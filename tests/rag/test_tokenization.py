from backend.rag.tokenization import HeuristicTokenCounter, TokenCounter


def test_heuristic_counter_handles_empty_text() -> None:
    counter = HeuristicTokenCounter()

    assert counter.count("") == 0
    assert counter.count(" \n\t") == 0


def test_heuristic_counter_counts_english_words_and_punctuation() -> None:
    counter = HeuristicTokenCounter()

    assert counter.count("Hello, world!") == 4
    assert counter.count("GP-UCB tunes K_p.") == 4


def test_heuristic_counter_does_not_collapse_cjk_text() -> None:
    counter = HeuristicTokenCounter()

    assert counter.count("高斯过程") == 4
    assert counter.count("中文 PID。") == 4


def test_heuristic_counter_is_deterministic_and_satisfies_protocol() -> None:
    counter = HeuristicTokenCounter()
    text = "M10 与 GP-UCB optimize J_seg."

    assert isinstance(counter, TokenCounter)
    assert counter.count(text) == counter.count(text)
