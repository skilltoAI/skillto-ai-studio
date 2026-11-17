"""Editable multilingual search hypotheses. Aliases do not prove AI provenance."""
from __future__ import annotations

import json
from pathlib import Path

LANGUAGES = {
    "en": {"ai": ["AI", "AI generated", "AI remake"],
           "dog": ["dog", "puppy", "doggo", "pupper"], "cat": ["cat", "kitten", "kitty", "meow"],
           "formats": ["dancing", "singing", "talking", "story", "meme", "pet photo animation", "motion transfer"]},
    "ja": {"ai": ["AI生成", "AI再現", "AIリメイク"],
           "dog": ["犬", "ワンコ", "わんちゃん", "子犬"], "cat": ["猫", "にゃんこ", "子猫", "ネコ"],
           "formats": ["踊る", "歌う", "しゃべる", "猫ミーム", "ペット写真 動画化"]},
    "de": {"ai": ["KI", "KI generiert", "KI Remake"],
           "dog": ["Hund", "Hunde", "Welpe", "Wauwau"], "cat": ["Katze", "Katzen", "Kätzchen", "Mieze"],
           "formats": ["tanzend", "singend", "sprechend", "Geschichte", "Meme", "Tierfoto animieren"]},
    "fr": {"ai": ["IA", "généré par IA", "recréé par IA"],
           "dog": ["chien", "chiot", "toutou"], "cat": ["chat", "chaton", "minou"],
           "formats": ["qui danse", "qui chante", "qui parle", "histoire", "mème", "animer photo animal"]},
}


def expand(seeds: list[str], languages: list[str]) -> dict:
    animals = []
    for seed in seeds:
        lowered = seed.casefold()
        if any(term in lowered for term in ("dog", "puppy", "犬", "hund", "chien")):
            animals.append("dog")
        if any(term in lowered for term in ("cat", "kitten", "猫", "katze", "chat")):
            animals.append("cat")
    animals = list(dict.fromkeys(animals))
    queries = []
    for lang in languages:
        if lang not in LANGUAGES:
            raise ValueError("Supported languages: en,ja,de,fr")
        words = LANGUAGES[lang]
        for animal in animals:
            core = words[animal][0]
            formats = [fmt.replace("猫ミーム", f"{core}ミーム") if lang == "ja" else fmt for fmt in words["formats"]]
            if lang == "fr":
                variants = [f"{core} {ai}" for ai in words["ai"]]
                variants += [f"{alias} IA" for alias in words[animal][1:]]
                variants += [f"{core} IA {fmt}" for fmt in formats]
            else:
                generated = f"KI-generierter {core}" if animal == "dog" else f"KI-generierte {core}"
                variants = [f"{ai} {core}" for ai in words["ai"]]
                if lang == "de":
                    variants[1] = generated
                variants += [f"{words['ai'][0]} {alias}" for alias in words[animal][1:]]
                variants += [f"{words['ai'][0]} {core} {fmt}" for fmt in formats]
            for query in dict.fromkeys(variants):
                queries.append(dict(query=query, language=lang, animal=animal, kind="proposed_search_term"))
    return dict(seeds=seeds, languages=languages, vocabulary={lang: LANGUAGES[lang] for lang in languages}, queries=queries,
                notes=["Generated linguistic hypotheses, not measured TikTok search volumes or established trend names.",
                       "Cat memes and pet nicknames can match real footage; inspect AI provenance separately.",
                       "Motion transfer/remake is separate from fully generated pets; retain the creator's evidence."])


def write_expansion(path: Path, seeds: list[str], languages: list[str]):
    result = expand(seeds, languages)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
