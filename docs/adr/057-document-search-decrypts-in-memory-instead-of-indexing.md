# Document Search decrypts in memory instead of keeping an index

Since ADR 031, `extracted_text` and `document_chunks.content` are ciphertext at rest, so the documents page search fell back to metadata (file name, description, type, Correspondent) while its placeholder still promised "auch im Dokumentinhalt". This ADR decides how Document Search reaches the text again, and what measuring it revealed about the chat.

## The decision

**Document Search matches words, in metadata and in the text, merged into the existing chronological list:**

- **Metadata**, by `ILIKE` as today.
- **Words in the text.** The backend decrypts `extracted_text` of all the Patient's Documents with the Patient KEK it already loads for the list, and matches the normalised term in Python: whitespace collapsed, hyphenation at line ends removed, `casefold()` (so "ß" matches "ss"). No fuzzy matching.

Every text hit carries a snippet, the passage around the word. The list stays chronological and filters as before; there is no ranking, and no AI call.

A family looking for a letter remembers a name, a drug, a case number. Typos and synonyms stay unsolved; the AI Health Assistant is the place for "the letter about his speech".

## The alternatives, and why not

- **A plaintext index (`tsvector`, `pg_trgm`).** Puts readable text, or its lexemes, back into the database at rest, which is what ADR 031 took out. Crypto-shredding a Patient would then also have to reach the index.
- **Blind-index tokens** (keyed hashes of each word). Keeps the database opaque, but supports only exact whole words, no substrings, no "Levetira" for "Levetiracetam", and is a second encrypted structure to keep in step with every reprocessing.
- **Semantic only.** It can miss the very letter in which the searched drug name stands verbatim.
- **Words plus similar topics by embedding**, labelled "ähnliches Thema". This was the first decision and was dropped after measuring it. On 250 chunks of one Patient's real letters, no distance separated related search terms from absent ones for either model. With `Qwen3-VL-Embedding-8B`, which hosted instances and the demo use, "Wetterbericht" came closer to the letters (0.28) than any related term did to its letters, so no cutoff let a single topic hit through without nonsense first. With `qwen3-embedding:4b`, 4 of 12 related terms passed before the first absent one. Medical terms the letters never mention ("Diabetes", "Hüftdysplasie") sit among the genuine ones.

## What this means for the chat

The same run measured whole questions, and it showed that `CHUNK_MAX_DISTANCE = 0.59` (ADR 038) filters nothing on hosted instances: with `Qwen3-VL-Embedding-8B` every unanswerable question lands at 0.52 or closer, so even a question about lasagne lists documents as its sources. The model was adopted in July on recall@10, which measures ranking, not distance, and the recalibration ADR 038 requires for a model change never happened. With `qwen3-embedding:4b` the July value still stops unrelated questions, but not medical ones the documents do not answer ("Hat sie Diabetes?", 0.43).

The chat stays as it is. A strict cutoff in context would make it answer "steht nicht in Ihren Unterlagen" for about half of the answerable questions, the false negative ADR 038 calls the worst outcome. A strict cutoff for the source list alone was considered, per embedding model (0.35 for `Qwen3-VL-Embedding-8B`, 0.425 for `qwen3-embedding:4b`), and rejected: on this corpus "Hat sie Diabetes?" lands at 0.355 and "Welche Sehstörung wurde festgestellt?" at 0.359, so the table would hinge on a few thousandths and drop the source of correct answers.

What makes this acceptable is what the same 20 questions showed when run through the real chat: every answerable one was answered from the right letter, named in the text, and every unanswerable one was declined without invention, including the medical ones. The model separates what the distance cannot. The source list is headed "Durchsuchte Dokumente", which is what it is, not a claim of relevance (ADR 038).

So `CHUNK_MAX_DISTANCE` keeps unrelated questions out for `qwen3-embedding:4b` and filters nothing for `Qwen3-VL-Embedding-8B`, and both are recorded rather than fixed. The calibration is `scripts/bench-retrieval.py --probes`, which prints only distances and the model name, never content. Its probes must include medical questions the documents do not answer; unrelated ones alone are why July looked separable.

## Consequences

- Each search decrypts every `extracted_text` of the Patient. That is cheap for hundreds of Documents and grows linearly; thousands per Patient is where a blind index or a per-request cache becomes worth its cost.
- A model change is still judged by recall, and its distances are measured with the script so the chat's cutoff is known to filter or not.
- The values come from one Patient, 250 chunks and 20 questions: a sample.
- Diary entries and Intake Forms are out of scope; a search across the whole record would be its own feature.

See also ADR 031 (per-Patient KEK), ADR 038 (chunk retrieval and its threshold), `docs/research-embedding-model.md`.
