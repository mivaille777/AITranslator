export type OverlayInteractionMode = "assistant" | "translation"

export type OverlayControlIntent =
  | { action: "enter_translation"; targetLanguage?: string }
  | { action: "exit_translation" }

const TARGET_LANGUAGE_ALIASES: Record<string, string> = {
  英文: "en",
  英语: "en",
  中文: "zh-CN",
  汉语: "zh-CN",
  日文: "ja",
  日语: "ja",
  韩文: "ko",
  韩语: "ko",
  法文: "fr",
  法语: "fr",
  德文: "de",
  德语: "de",
}

const GENERIC_TRANSLATION_PATTERNS = [
  /^翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^帮我翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^我要你翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^请翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^把(?:这段|这个|它|选中的内容)?翻译(?:一下|下)?[。！! ]*$/i,
  /^(?:请|帮我|我要你|能不能|可以(?:帮我)?)?(?:把)?(?:这段|这个|它|选中的内容)?(?:翻译|译)(?:一下|下)?[吗呢]?[？?。！! ]*$/i,
  /^(?:进入|打开|开始|切到|切换到)(?:翻译|翻译模式|翻译界面|翻译工作区)[。！! ]*$/i,
  /^继续翻译[。！! ]*$/i,
  /^translate(?: this| it| the selection)?[.! ]*$/i,
  /^please translate(?: this| it| the selection)?[.! ]*$/i,
  /^can you translate(?: this| it| the selection)?[?!. ]*$/i,
  /^(?:open|enter|start|switch to) translation(?: mode| workspace)?[.! ]*$/i,
  /^continue translating[.! ]*$/i,
]

const EXIT_TRANSLATION_PATTERNS = [
  /^翻译(?:完了|好了|完成了|结束了)[。！! ]*$/i,
  /^翻译(?:完成|结束)[。！! ]*$/i,
  /^(?:退出|关闭|结束|离开)(?:当前)?(?:的)?翻译(?:模式|界面|工作区)?[。！! ]*$/i,
  /^(?:不用|不需要|别|停止|停下)(?:再)?翻译(?:了)?[。！! ]*$/i,
  /^(?:回到|返回)(?:AI|助手|assistant|聊天|对话)(?:模式|界面)?[。！! ]*$/i,
  /^继续(?:聊天|对话)[。！! ]*$/i,
  /^(?:done|finished) translating[.! ]*$/i,
  /^translation (?:done|finished|complete)[.! ]*$/i,
  /^(?:exit|close|leave|stop) translation(?: mode| workspace)?[.! ]*$/i,
  /^back to (?:assistant|chat)[.! ]*$/i,
  /^continue (?:chatting|the conversation)[.! ]*$/i,
]

const TARGET_LANGUAGE_COMMAND = new RegExp(
  `^(?:请|帮我|我要你|能不能|可以(?:帮我)?)?(?:把)?(?:这段|这个|它|选中的内容)?(?:翻译|翻|译)(?:一下|下)?(?:成|为)?(${Object.keys(TARGET_LANGUAGE_ALIASES).join("|")})[吗呢]?[？?。！! ]*$`,
  "i",
)

export function resolveOverlayControlIntent(
  value: string,
  mode: OverlayInteractionMode,
): OverlayControlIntent | null {
  const normalized = value.trim()
  if (!normalized) return null

  if (
    mode === "translation" &&
    EXIT_TRANSLATION_PATTERNS.some((pattern) => pattern.test(normalized))
  ) {
    return { action: "exit_translation" }
  }

  const targetMatch = normalized.match(TARGET_LANGUAGE_COMMAND)
  if (targetMatch) {
    const targetLanguage = TARGET_LANGUAGE_ALIASES[targetMatch[1]]
    if (targetLanguage) {
      return { action: "enter_translation", targetLanguage }
    }
  }

  if (GENERIC_TRANSLATION_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return { action: "enter_translation" }
  }

  return null
}
