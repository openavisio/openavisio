#!/usr/bin/env python3
"""A page with prose and a table loses neither under glm-ocr (#246).

glm-ocr's "Table Recognition:" returns the table and drops the letter around it.
Run directly or under pytest.
"""
import vision_ocr


class _Backend:
    def __init__(self):
        self.prompts = []

    def chat(self, model, messages, images=None, num_ctx=None):
        prompt = messages[0]["content"]
        self.prompts.append(prompt)
        return {"Text Recognition:": " Beurteilung: Epilepsie. ",
                "Table Recognition:": "<table><tr><td>Natrium</td></tr></table>"}.get(prompt, "Seite")


def _read(model, table_like):
    saved = vision_ocr.analyze_page
    vision_ocr.analyze_page = lambda _: {"table_like": table_like}
    try:
        backend = _Backend()
        return vision_ocr._read_page(backend, model, b"png"), backend.prompts
    finally:
        vision_ocr.analyze_page = saved


def test_glm_table_page_keeps_the_prose():
    text, prompts = _read("glm-ocr:Q8_0", True)
    assert prompts == ["Text Recognition:", "Table Recognition:"]
    assert text == "Beurteilung: Epilepsie.\n\n<table><tr><td>Natrium</td></tr></table>"


def test_glm_text_page_is_one_pass():
    assert _read("glm-ocr:Q8_0", False)[1] == ["Text Recognition:"]


def test_other_models_read_a_page_in_one_pass():
    assert _read("lightonai/LightOnOCR-2-1B", True)[1] == [vision_ocr.VISION_OCR_PROMPT]


if __name__ == "__main__":
    test_glm_table_page_keeps_the_prose()
    test_glm_text_page_is_one_pass()
    test_other_models_read_a_page_in_one_pass()
    print("ok")
