"""Counterpoint tutor prompt + Claude wrapper.

Reuses the existing claude_client transport, but swaps the system prompt
for one tailored to species-counterpoint feedback. The user prompt is
generated from the AnalysisResult of running species_runner.
"""

from __future__ import annotations

import logging
import os

import anthropic

from ..llm.claude_client import DEFAULT_MAX_TOKENS, DEFAULT_MODEL
from ..llm.prompt_builder import build_user_prompt
from ..model.issue import AnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたはFux/Jeppesen 流の対位法を教える、厳しくも温かい個人教師です。
生徒(作曲家)は種対位法 (Species Counterpoint) を練習していて、
今その課題を提出してきました。あなたの仕事は以下の通りです:

1. 検出された各問題について、教科書的な用語で診断する
   (例: 平行5度、準備されていない不協和、釣り合わない跳躍など)。
2. 「絶対的な禁則」(完全音程の平行進行、1種での強拍不協和、旋律的三全音など)と
   「スタイル上の好ましさ」(解決されていない跳躍、クライマックスの重複など)を
   明確に分けて伝える。
3. 直し方は必ず Studio One 表記の音名で具体的に書く
   (中央C = C3、例: 「Bar 4 の F3 を D3 に変える」)。
   可能なら2案出して、生徒が選べるようにする。
4. 良い箇所も褒める — 旋律線の形が良いところ、反進行がうまく使えているところ、
   クライマックスがうまく配置されているところを言葉にする。
5. 最後に「全体としての判定(1文)」と「次の練習で意識すべき1点」をまとめる。

トーン: 親切で焦点の絞れた個人教師。簡潔に、説教臭くならず。
音程は必ず音名で(抽象的な度数だけで終わらない)。

**必ず日本語で返答してください**。英語の用語(parallel fifth など)を使う場合も、
最初に日本語訳を併記する形で。
"""


def build_tutor_prompt(result: AnalysisResult, species: int = 1) -> str:
    base = build_user_prompt(result)
    return (
        f"# 種対位法エクササイズ(Species {species})\n\n"
        + base
        + "\n\n# あなたへのリクエスト\n"
        "**日本語で**返答してください。各問題について次の構成で番号付きセクションを書いてください:\n"
        "1. 診断(対位法用語で簡潔に1文)\n"
        "2. 重大度: 禁則 / スタイル上の好ましさ / 軽微\n"
        "3. 具体的な修正案(Studio One 表記の音名で。可能なら2案)\n"
        "4. (任意)その修正でどう改善されるか\n\n"
        "番号付き問題を全部書き終えたら、最後に:\n"
        "- '## 良かった点' — 短い箇条書きを2つ\n"
        "- '## 次の練習目標' — 具体的に1つ\n"
        "を続けてください。\n"
    )


def critique_species(
    result: AnalysisResult,
    species: int = 1,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it before requesting tutor feedback."
        )

    prompt = build_tutor_prompt(result, species=species)
    logger.info(
        "Calling Claude tutor (%s) species=%d, prompt length=%d chars",
        model, species, len(prompt),
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if hasattr(b, "text"))
