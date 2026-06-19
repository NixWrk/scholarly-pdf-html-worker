from __future__ import annotations

import re

from pdf_html_polish.quality_loop.audit_blocks import Defect, diagnostic_text, snippet
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect


KNOWN_OCR_TOKEN_RE = re.compile(
    r"\b(?:iournal\.pone|inital|neabling|Segmentaion|simpification|systometry|"
    r"urflowmetry|urtheral|validtation|seperable|pngpng|Uroflowmetery|"
    r"flowmetery|bootloding|Examing|Parametres|Rewiev|microconroller|"
    r"Mirocontroller|premicturtion|Nusssenblatt|temprature|childrean|"
    r"ulimate|three-dimensioanl|Tree-dimensional|Wherev\s*\d)\b|"
    r"\bDmax=Dminw1:5\b|\bpv0:\d+\b|\b0:5mLs\{?|\bhealth\s+male\s+volunteer\b|"
    r"\bwill\s+to\s+help\b|\beffici[^\w\s]{1,3}ency\b|\b0\.999\s+0995\b|"
    r"\b(?:effekt|retrospekt|qualitat)\s+iv\b|\bAPPEND\s+ix\b|"
    r"\bINTEL\s+i\s+LIGENT\b|\bQavg\s+and\s+Omax\b|\bVol\s+ofmoved\b|"
    r"\bcognitive\s+iter\b|\bsys-\s+tem\b|\bI\s+mplantable\b|"
    r"\bdocuments\s+that\s+that\s+intensity\b|\baesthesia\b|\bMagr\s+Reson\b|"
    r"\btelsa\b|\bMata-Analysis\b|\bcorrela\s+ition\b|\bcor\s+relation\b|"
    r"\braw\s+dat\s+a\b|\bRetinal\s+Nerve\s+Fiber\s+Laver\b|"
    r"\bAmercian\s+ophthalmological\s+society\b|\bbulbocarnosus\b|"
    r"\bqualify\s+factor\b|\blength\s+form\s+ADF4351\b|"
    r"\bdeceases\s+as\s+the\s+distance\b|\bUniverisity\b|\bMEME\s+sensors\b|"
    r"\bBolognia\b|\b63\s+DPhotoWorks\b|\bBulato\s+v\.\b|"
    r"\br=0\.9\s+(?:840|526)\b|\bfMR\s+i\b|"
    r"\b3\s+1\s+mm\s+female\s+human\s+brain\b|\bMu&es\b|\bHaiiy\b|"
    r"\bCruc\$xion\b|\bthev\b|\bP\s+to\s+bc\b|\bE\s+clarity\b|"
    r"\bparameter\s+a'\s+is\s+Eq\.\s*\(1\)\b|\bD_\{eve\}\b|"
    r"\bD'_\{\\rm\s+eve\}\b|\bb5223\b|\bDl5660620\b|\b2u560\b|"
    r"\bDl50\.4\b|\b9\s+m\s+m\b|\bF\s+1\s+8\b|"
    r"\bflow\s+flow\s+flow\s+flow\b|\bLiverposl\b|\bcomparision\b|"
    r"\bObject\s+Eden260V\b|\bWothlytype\b|\b20th-\s+and\s+21\s+st-century\b|"
    r"\belectromyograhic\b|\binvolunatary\b|\bclincal\b|\bsymphisis\b|"
    r"\bAmerican\s+Society\s+of\s+Clinical\s+Ncology\b|\bFlorescence\s+Technique\b|"
    r"\bTQma\s+x\b|\bVoiding\s+positing\b|\bsignificate\s+statistical\b|"
    r"\bpassive\s+senor\b|\bUrdynamic\b|\burinary\s+track\b|"
    r"\bInternational\s+continent\s+society\b|\bnon-invasivly\b|"
    r"\bhome\s+urofowmetry\b|\bRefrence\b|\bFERENCE\s+VALUES\b|"
    r"\b(?:Qrnax|TQrnax|TlOO|Q2sea)\b|\bclassifified\b|"
    r"\bNeurocsi\b|\bHip-pocampus\b|\bIPSS\s+0\s*=\s*10\s+symptoms\b|"
    r"\bDWT\s+values\s+-2\s+mm\b|\bgrade\s+1\u00bc0\b|"
    r"\bbeacause\b|\b\u03a4he\s+touch\s+map\b|\b\u0399mproving\b|"
    r"\bthrefore\b|\beBDetheque\b|\ban\s+notate\b|"
    r"\bform\s+eBDtheque\b|\bcompliment\s+of\s+the\s+text-area\s+mask\b|"
    r"\b0000-0003-4044-\s+0927\b|"
    r"\b(?:5\.22|4\.21|5\.13)\s+\\pm\s+2,\s+(?:38|36|40)\b|"
    r"\b(?:Schfer|Standarisation|subcomitee|standarization|aformentioned|Cvalli|"
    r"Routeledge)\b|\bPdetQma\s+x\b|\bBOO\s+i\b|\bIPP\s+Grade\s+(?-i:iii)\b|"
    r"\bsimulates\s+the\s+The\s+validation\b|\bto\s+be\s+The\s+topological\s+sort\b|"
    r"\bDirectX-\s+R\b|"
    r"\b(?:MDP\s+i|ISTOR|Appel's\s+Sir\s+i|Build-in\s+sensors|"
    r"Sem\s+i\s*-\s*structured|Gen-A\s+i|Numbe\s+er|parti\s+cipants|"
    r"nterview|Ggather|Vorkshop|ocus\s+group|ANACCESSIBLE|(?-i:TOOTEKO)|"
    r"Deptartment|fascade|basrelif|Mulitmodal|agumentation|"
    r"Archelological|Museum\s+of\s+Moden\s+Art|Deparment|Polywoks|"
    r"PRAVALENCE|pvalue\s*[<=>]|IPelvic|hispareunia|main:\s+\d|"
    r"characteriscs|obeserved|stuies|miduretrhal|incotinence|resultes|"
    r"intrauethral|oncontinence|Urologiy|OUALITY|QLO\s+C30|"
    r"istopaholohical|compilated|Continues\s+variables|San\s+Gerardoo|"
    r"catherization|preferrable|postvoding|Thirtyeight|electronical|"
    r"oraotten|PATRATS|STLAR|throughour|This\s+ing\s+with\s+Fig\.?\s*1|"
    r"elipse|couse-quence|Dipping\s+Robs|daguerrectype|negitive|"
    r"sclution|iedide|Cutring|proccss|Negavives|precipated|cunce|"
    r"14\s+C-beled|Shep(?:a|ha)dex|trimetylsilyl|dihydroxyated|"
    r"defensen|Rgiht|Verebrate|millenium|Foundayion|Naturwissenschaftem|"
    r"super\s+prescription\s+of\s+H3|secondsmm-2|sequence4|FA\s+330|"
    r"Ote\s+this:\s+DO|ARTI\s+CLE\s+TYPE|Accepted\s+Manuscrip|"
    r"room\s+temperation|Enzymelinked|attempeted|detecte|afrer|"
    r"tranformed|coditions|realtive|occurance|oberved|imlied|"
    r"speices|Furhtermore|responsed|treaditional|around287\.8|"
    r"Abstrac\s+t|F\s+igures|Acknow\s+rledgements|Chapte\s+r|"
    r"Append\s+i\s+ces|Apper\s+ndi\s+x|Bibliogra\s+phy|p,\s*pj\]of|"
    r"left\)999|fotograf\s+ii|London1843|co\s+verage|approximatley|"
    r"chronologicall\s+y|Archtecture|Woodsawer|Learning\s+R\s+ates|"
    r"Vacla\s+v|Date\s+o\s+of\s+mailing|Autho\s+Authorized|"
    r"patent\s+family\s+anne\s+x|hiah\s+camera|"
    r"In\s+some\s+\[880\]\s+embodiments|Marvland|OceanofPDF\.com|"
    r"Avoiraupois|appro\s+ximately|weigh\s+ght|(?-i:bH)|F\s+011\s+07|"
    r"Avo\s+i\s+irdupois|Chroming\s+and\s+Auditor\s+Spring\s+Inc\.|"
    r"ERTAINTY|acctone|pathologica|essenetial|USMLE:pPotential|"
    r"Constitutional\s+Al|GAL\s+such\s+as|"
    r"Al(?:\s+(?:techniques|Office|triad|systems|interventions|education|"
    r"feedback|driven|generated|based)|-driven|-generated|-based)|"
    r"euromodulation\s+devices|crania\s+l\s+implant|Bultimore|"
    r"Stoimeno\s+v\.|list\s+all\s+the\s+they\s+identified|"
    r"OPRATING\s+PRICIPLE|discription|milivolt|upto|coma\s+separated|"
    r"purposed\s+work|millitres|ghraph|Authers|"
    r"Electronic\(Cambridge|If\s+inal|best\s+suites|Stocks\s+shift|"
    r"nanomicells|plent|toxity|uroflometer|31\.6\s+8\s+C|35\.9\s+8\s+C|"
    r"3[67]8C|425\s+cmH2O|460\s+bpm)\b|"
    r"\bODs/MB\b|"
    r"\bet\s+nl\.|\bHands\s+of!|\bComputer\s+Based\s+Method\s+\?|"
    r"\.oog-inch\b",
    re.IGNORECASE,
)


def known_ocr_token_is_false_positive(plain: str, match: re.Match[str]) -> bool:
    token = match.group(0)
    if token.upper() == "ELIPSE":
        context = plain[max(0, match.start() - 16) : min(len(plain), match.end() + 16)]
        return re.search(r"\bIRIT\s*-\s*ELIPSE\b", context, re.IGNORECASE) is not None
    if token == "Wothlytype":
        context = plain[max(0, match.start() - 120) : min(len(plain), match.end() + 120)]
        return re.search(r"\b(?:collodion|albumen|surface|coating|print)\b", context, re.IGNORECASE) is not None
    if token == "OceanofPDF.com":
        return True
    if token == "63 DPhotoWorks":
        context = plain[max(0, match.start() - 120) : min(len(plain), match.end() + 120)]
        return "DPhotoWorks website" in context or "3DPhotoWorks" in context
    if token == "3 1 mm female human brain":
        context = plain[max(0, match.start() - 160) : min(len(plain), match.end() + 160)]
        return "additional projects were published" in context.lower()
    if token.lower() == "cognitive iter":
        context = plain[max(0, match.start() - 160) : min(len(plain), match.end() + 160)]
        return re.search(r"\bhaptic\s+exploration\b", context, re.IGNORECASE) is not None
    if token == "TOOTEKO":
        context = plain[max(0, match.start() - 120) : min(len(plain), match.end() + 160)]
        return re.search(r"\bcase\s+study\s+of\s+augmented\s+reality\b", context, re.IGNORECASE) is not None
    return False


def known_ocr_token_is_present_in_pdf_text_layer(token: str, pdf_text: str) -> bool:
    if not token or not pdf_text:
        return False
    token_norm = diagnostic_text(token).lower()
    if len(token_norm) < 4:
        return False
    pdf_norm = diagnostic_text(pdf_text).lower()
    if token_norm in pdf_norm:
        return True
    token_words = re.findall(r"[a-z0-9\u0370-\u03ff]+", token_norm, flags=re.IGNORECASE)
    if len(token_words) < 2:
        return False
    return re.search(r"\s+".join(re.escape(word) for word in token_words), pdf_norm, re.IGNORECASE) is not None


def known_ocr_token_defects(plain: str, pdf_text: str, *, stage: str) -> list[Defect]:
    known_ocr_match = KNOWN_OCR_TOKEN_RE.search(plain)
    if known_ocr_match is None or known_ocr_token_is_false_positive(plain, known_ocr_match):
        return []

    known_ocr_extra: dict[str, object] = {"match": known_ocr_match.group(0)}
    if known_ocr_token_is_present_in_pdf_text_layer(known_ocr_match.group(0), pdf_text):
        known_ocr_extra.update(
            {
                "quality_counted": False,
                "source_pdf_text_layer_evidence": "known OCR token is already present in the source PDF text layer",
            }
        )

    return [
        make_defect(
            defect_id="P71",
            cc_class="CC-04/CC-13",
            check="Known OCR token or phrase remains in polish text",
            severity="warning",
            block=None,
            snippet=snippet(plain, known_ocr_match.start(), known_ocr_match.end()),
            stage=stage,
            hypothesis="Manual full-text review found recurring OCR token shapes that the broader audit did not classify.",
            proposed_fix_layer="EN polish OCR residue scanner",
            regression_test=(
                "Tokens such as 'urflowmetry', 'urtheral', 'premicturtion', "
                "'Qavg and Omax', and malformed p-values are reported."
            ),
            extra=known_ocr_extra,
        )
    ]
