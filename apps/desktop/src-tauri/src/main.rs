#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    sync::atomic::{AtomicU64, Ordering},
    thread,
    time::Duration,
};
use tauri::{Manager, PhysicalPosition};

static OVERLAY_MOVE_GENERATION: AtomicU64 = AtomicU64::new(0);

fn next_overlay_move_generation() -> u64 {
    OVERLAY_MOVE_GENERATION.fetch_add(1, Ordering::SeqCst) + 1
}

#[tauri::command]
fn cancel_overlay_motion() {
    next_overlay_move_generation();
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
    let start = overlay.outer_position().map_err(|error| error.to_string())?;
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
        .invoke_handler(tauri::generate_handler![
            animate_overlay_position,
            cancel_overlay_motion
        ])
        .run(tauri::generate_context!())
        .expect("error while running AITranslator desktop shell");
}
