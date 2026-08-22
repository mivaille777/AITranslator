#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    sync::atomic::{AtomicU64, Ordering},
    thread,
    time::Duration,
};
use tauri::{Manager, PhysicalPosition};

static OVERLAY_MOVE_GENERATION: AtomicU64 = AtomicU64::new(0);
const OVERLAY_CORNER_RADIUS_CSS_PX: f64 = 24.0;

#[cfg(windows)]
fn apply_overlay_window_region(window: &tauri::WebviewWindow) -> Result<(), String> {
    use windows_sys::Win32::Foundation::HWND as Win32Hwnd;
    use windows_sys::Win32::Graphics::Gdi::{
        CreateRoundRectRgn, DeleteObject, SetWindowRgn, HGDIOBJ,
    };

    let hwnd = window.hwnd().map_err(|error| error.to_string())?;
    let size = window.outer_size().map_err(|error| error.to_string())?;
    let scale_factor = window.scale_factor().map_err(|error| error.to_string())?;
    let width = i32::try_from(size.width).map_err(|_| "overlay width is too large")?;
    let height = i32::try_from(size.height).map_err(|_| "overlay height is too large")?;

    if width <= 0 || height <= 0 {
        return Err("overlay window has an invalid size".to_string());
    }

    let radius = (OVERLAY_CORNER_RADIUS_CSS_PX * scale_factor)
        .round()
        .clamp(1.0, f64::from(width.min(height) / 2)) as i32;
    let region = unsafe { CreateRoundRectRgn(0, 0, width, height, radius * 2, radius * 2) };

    if region.is_null() {
        return Err("CreateRoundRectRgn failed".to_string());
    }

    let result = unsafe { SetWindowRgn(hwnd.0 as Win32Hwnd, region, 1) };
    if result == 0 {
        unsafe {
            DeleteObject(region as HGDIOBJ);
        }
        return Err("SetWindowRgn failed".to_string());
    }

    // SetWindowRgn takes ownership of `region` after a successful call.
    Ok(())
}

#[cfg(not(windows))]
fn apply_overlay_window_region(_window: &tauri::WebviewWindow) -> Result<(), String> {
    Ok(())
}

fn next_overlay_move_generation() -> u64 {
    OVERLAY_MOVE_GENERATION.fetch_add(1, Ordering::SeqCst) + 1
}

#[tauri::command]
fn cancel_overlay_motion() {
    next_overlay_move_generation();
}

fn resolve_window(
    app: &tauri::AppHandle,
    window_label: &str,
) -> Result<tauri::WebviewWindow, String> {
    app.get_webview_window(window_label)
        .ok_or_else(|| format!("window '{window_label}' is unavailable"))
}

#[tauri::command]
fn window_minimize(app: tauri::AppHandle, window_label: String) -> Result<(), String> {
    resolve_window(&app, &window_label)?
        .minimize()
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn window_toggle_maximize(app: tauri::AppHandle, window_label: String) -> Result<bool, String> {
    let window = resolve_window(&app, &window_label)?;
    let is_maximized = window.is_maximized().map_err(|error| error.to_string())?;

    if is_maximized {
        window.unmaximize().map_err(|error| error.to_string())?;
    } else {
        window.maximize().map_err(|error| error.to_string())?;
    }

    Ok(!is_maximized)
}

#[tauri::command]
fn window_is_maximized(app: tauri::AppHandle, window_label: String) -> Result<bool, String> {
    resolve_window(&app, &window_label)?
        .is_maximized()
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn window_close(app: tauri::AppHandle, window_label: String) -> Result<(), String> {
    resolve_window(&app, &window_label)?
        .close()
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn update_overlay_window_shape(app: tauri::AppHandle) -> Result<(), String> {
    let overlay = app
        .get_webview_window("overlay")
        .ok_or_else(|| "overlay window is unavailable".to_string())?;

    apply_overlay_window_region(&overlay)
}

#[tauri::command]
fn animate_overlay_position(
    app: tauri::AppHandle,
    x: i32,
    y: i32,
    duration_ms: u64,
) -> Result<(), String> {
    let overlay = app
        .get_webview_window("overlay")
        .ok_or_else(|| "overlay window is unavailable".to_string())?;
    let start = overlay
        .outer_position()
        .map_err(|error| error.to_string())?;
    let generation = next_overlay_move_generation();
    let delta_x = x - start.x;
    let delta_y = y - start.y;
    let distance = ((delta_x as f64).powi(2) + (delta_y as f64).powi(2)).sqrt();

    if duration_ms == 0 || distance > 720.0 {
        overlay
            .set_position(PhysicalPosition::new(x, y))
            .map_err(|error| error.to_string())?;
        return Ok(());
    }

    thread::spawn(move || {
        // Keep native motion short and responsive. Doing the interpolation here avoids
        // one WebView -> Tauri IPC round-trip for every animation frame.
        let frame_ms = 8_u64;
        let steps = (duration_ms.div_ceil(frame_ms)).clamp(7, 15) as i32;

        for step in 1..=steps {
            if OVERLAY_MOVE_GENERATION.load(Ordering::Relaxed) != generation {
                return;
            }

            let t = step as f64 / steps as f64;
            let eased = 1.0 - (1.0 - t).powi(3);
            let next_x = start.x as f64 + delta_x as f64 * eased;
            let next_y = start.y as f64 + delta_y as f64 * eased;

            if overlay
                .set_position(PhysicalPosition::new(
                    next_x.round() as i32,
                    next_y.round() as i32,
                ))
                .is_err()
            {
                return;
            }

            if step < steps {
                thread::sleep(Duration::from_millis(frame_ms));
            }
        }
    });

    Ok(())
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            if let Some(overlay) = app.get_webview_window("overlay") {
                if let Err(error) = apply_overlay_window_region(&overlay) {
                    eprintln!("failed to initialize overlay window region: {error}");
                }

                let overlay_for_resize = overlay.clone();
                overlay.on_window_event(move |event| {
                    if matches!(
                        event,
                        tauri::WindowEvent::Resized(_)
                            | tauri::WindowEvent::ScaleFactorChanged { .. }
                    ) {
                        if let Err(error) = apply_overlay_window_region(&overlay_for_resize) {
                            eprintln!("failed to update overlay window region: {error}");
                        }
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            animate_overlay_position,
            cancel_overlay_motion,
            window_minimize,
            window_toggle_maximize,
            window_is_maximized,
            window_close,
            update_overlay_window_shape
        ])
        .run(tauri::generate_context!())
        .expect("error while running AITranslator desktop shell");
}
