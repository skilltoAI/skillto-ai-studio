# Keyword expansion and ranking

Separate three layers: seed intent, proposed search vocabulary, and actually observed trend aliases. The bundled `keywords.py` supplies editable linguistic candidates for AI dog/cat. These are not evidence that a phrase is popular or a native community's established nickname.

| Language | Dog / nicknames | Cat / nicknames | Generation / remake modifiers |
| --- | --- | --- | --- |
| English | dog, puppy, doggo, pupper | cat, kitten, kitty, meow | AI generated, AI remake, motion transfer, pet photo animation |
| Japanese | 犬, 子犬, ワンコ, わんちゃん | 猫, 子猫, ネコ, にゃんこ | AI生成, AI再現, AIリメイク, 写真を動画化 |
| German | Hund, Hunde, Welpe, Wauwau | Katze, Katzen, Kätzchen, Mieze | KI generiert, KI Remake, Tierfoto animieren |
| French | chien, chiot, toutou | chat, chaton, minou | généré par IA, recréé par IA, animer photo animal |

Formats worth proposing: dancing, singing/lip sync, talking, story, meme, pet photo animation and motion transfer; translate as relevant. Distinguish remaking an existing dance/meme with a pet from fully synthetic animals. Tool names alone identify neither the subject nor the production technique. “猫ミーム”, meow and pet nicknames can match real footage; pair them with AI terms and inspect content. `chat` is ambiguous in French/English; use `chat IA` or `chat généré par IA` rather than unqualified `chat`.

Add actual trend titles, sounds, creator handles and spelling variants only after finding dated evidence. Preserve their source URLs and whether the evidence is original or secondary. Search-engine snippets and articles can supply leads; they do not count toward primary collected videos or a 1,000-video acceptance target.

## Sampling

Use multiple languages and variants, round robin across language and animal groups. Search queries use normal rendered pages and browser-driven scrolling. Checkpoint the deduplicated video pool and per-query outcomes. Record failures rather than repeatedly requesting an empty/restricted endpoint. Resume only the same subject and session scope. If collecting at least 1,000, the acceptance count is distinct TikTok IDs actually captured from search responses, including older results; report the number falling inside the recent window separately. If the user requires 1,000 *recent eligible* videos, continue until that narrower count reaches 1,000.

The query report includes application status codes, HTTP/gate failures, per-query new unique counts, captured timestamps and coverage. Search is influenced by session, location, relevance and platform ranking. “Most popular” means highest observed views in this documented sample. It is not evidence of exhaustive/global coverage. Language of the query is not a region/language classifier for returned videos.

## Screening and thresholds

1. Restrict publish time to the rolling last 30 UTC days, excluding future dates. Use full timestamps from JSON, not month/day DOM labels or video ID dates.
2. Verify each promoted video's author using profile JSON matched to its stable author IDs. Do not substitute visible handle text for ownership proof.
3. Review actual title, cover, source page/clip, AI label and creator statements. Keep explicit production type: generated, remake/motion transfer, tutorial, unverified. Exclude tutorials and ordinary animal footage from a content-only chart. A platform AI flag or self-description is an attributed claim, not an independent detection result.
4. Rank by current observed plays. Keep unavailable plays unknown; do not rank by likes while calling it a views chart. Include counts and capture time.
5. Low-follower viral default is `0 < followers <= 10000 AND views >= 100000 AND views/followers >= 10`. All thresholds configurable. Missing/zero followers are unqualified/unknown. Followers are measured at capture; the service cannot reconstruct followers at publication.
6. Preserve all metrics and source links, plus ratio and exact qualification reasons. Put low-follower results in a separate review table. Do not conflate this rule with the account collect/share mean rule.
