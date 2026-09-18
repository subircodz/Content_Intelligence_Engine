# Multilingual Content Output

The Content Intelligence Engine can generate the final article/document draft in:

- English
- Telugu (తెలుగు)
- Tamil (தமிழ்)

Research, evidence validation, competitor intelligence, and SEO/AIO/GEO strategy remain the same. Language selection controls the generated article and DOCX presentation; it does not translate or alter the underlying evidence.

## Telugu

Use:

    content-intelligence-engine --language telugu "మీ ఆర్టికల్ అంశం"

Or set:

    CONTENT_LANGUAGE=telugu

The output is written to a language-specific DOCX filename ending in -telugu.docx.

## Tamil

Use:

    content-intelligence-engine --language tamil "உங்கள் கட்டுரை தலைப்பு"

Or set:

    CONTENT_LANGUAGE=tamil

The output is written to a language-specific DOCX filename ending in -tamil.docx.

## English

English remains the default for backward compatibility:

    content-intelligence-engine --language english "Your article topic"

## Accuracy boundary

The LLM is instructed to preserve verified facts, numbers, dates, names, entities, and evidence while writing the prose in the requested language. Language generation does not make an unsupported claim authoritative.

The final document is still a draft for human editorial review.
