# Content Intelligence Engine — తెలుగు డాక్యుమెంటేషన్

Content Intelligence Engine ఒక topic మరియు target website ఆధారంగా research-backed content strategy మరియు human-reviewable article draft ను రూపొందిస్తుంది.

## ఇది ఏమి చేస్తుంది

Pipeline:

Topic + Target Domain → Research → Competitor Intelligence → Quality Gate → SEO/AIO/GEO Strategy → Article Draft → DOCX

Generated content ను స్వయంచాలకంగా publish చేయదు. Final editorial review అవసరం.

## తెలుగు output

CLI:

    content-intelligence-engine --language telugu "మీ ఆర్టికల్ అంశం"

లేదా environment లో:

    CONTENT_LANGUAGE=telugu

తెలుగు output DOCX filename లో -telugu suffix ఉంటుంది.

## Tamil output

    content-intelligence-engine --language tamil "உங்கள் கட்டுரை தலைப்பு"

## Configuration

కనీసం production లో ఇవి అవసరం:

    TARGET_DOMAIN=example.com
    LLM_BASE_URL=https://llm.example.com/v1
    LLM_MODEL=your-model

Output language కోసం:

    CONTENT_LANGUAGE=telugu

లేదా:

    CONTENT_LANGUAGE=tamil

CLI లో --language ఇచ్చినప్పుడు అది CONTENT_LANGUAGE ను override చేస్తుంది.

## Accuracy

Research evidence, verified facts, numbers, dates, names మరియు entities ను language generation సమయంలో మార్చకూడదని writer కు instruction ఉంటుంది. LLM-generated prose స్వయంగా factual evidence కాదు.

## పూర్తి operational documentation

Production setup, security మరియు live validation కోసం English documentation:

- docs/PRODUCTION.md
- SECURITY.md
- docs/LANGUAGES.md
