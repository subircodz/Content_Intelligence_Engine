# Content Intelligence Engine — தமிழ் ஆவணம்

Content Intelligence Engine ஒரு topic மற்றும் target website அடிப்படையில் research-backed content strategy மற்றும் human-reviewable article draft ஐ உருவாக்குகிறது.

## இது என்ன செய்கிறது

Pipeline:

Topic + Target Domain → Research → Competitor Intelligence → Quality Gate → SEO/AIO/GEO Strategy → Article Draft → DOCX

உருவாக்கப்பட்ட content தானாக publish செய்யப்படாது. இறுதி editorial review தேவை.

## தமிழ் output

CLI:

    content-intelligence-engine --language tamil "உங்கள் கட்டுரை தலைப்பு"

அல்லது environment:

    CONTENT_LANGUAGE=tamil

தமிழ் output DOCX filename இல் -tamil suffix இருக்கும்.

## Telugu output

    content-intelligence-engine --language telugu "మీ ఆర్టికల్ అంశం"

## Configuration

Production இல் குறைந்தபட்சமாக:

    TARGET_DOMAIN=example.com
    LLM_BASE_URL=https://llm.example.com/v1
    LLM_MODEL=your-model

Output language:

    CONTENT_LANGUAGE=tamil

அல்லது:

    CONTENT_LANGUAGE=telugu

CLI இல் --language கொடுத்தால் அது CONTENT_LANGUAGE-ஐ override செய்யும்.

## Accuracy

Research evidence, verified facts, numbers, dates, names மற்றும் entities ஆகியவற்றின் பொருளை மாற்றாமல் requested language-ல் prose உருவாக்க writer-க்கு instruction வழங்கப்படுகிறது. LLM-generated prose மட்டும் factual evidence ஆக கருதப்படாது.

## முழுமையான operational documentation

Production setup, security மற்றும் live validation:

- docs/PRODUCTION.md
- SECURITY.md
- docs/LANGUAGES.md
