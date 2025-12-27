"""
FOTZ Ebook Factory - Mikroserwis PDF
=====================================
Gotowy do wdrożenia na Railway.

Endpointy:
- POST /generate-pdf - Generuje PDF z przetłumaczonej treści
- POST /generate-zip - Generuje kompletny pakiet ZIP
- GET /health - Health check

Autor: FOTZ Studio
"""

import os
import re
import io
import zipfile
import tempfile
import requests
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

import markdown
from weasyprint import HTML, CSS
from PyPDF2 import PdfMerger
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# =============================================================================
# KONFIGURACJA
# =============================================================================

app = FastAPI(
    title="FOTZ PDF Microservice",
    description="Mikroserwis do generowania PDF dla FOTZ Ebook Factory",
    version="1.0.0"
)

# CORS - pozwól na połączenia z Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # W produkcji ogranicz do domeny Lovable
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kolory FOTZ
BRANDING = {
    "primary_color": "#601A43",      # Burgundowy
    "secondary_color": "#162E52",    # Navy Blue
    "accent_color": "#C9A227",       # Złoty
}

PAGE_WIDTH, PAGE_HEIGHT = A4

# =============================================================================
# MODELE PYDANTIC
# =============================================================================

class TocItem(BaseModel):
    title: str
    page: int

class PdfRequest(BaseModel):
    content: str  # Przetłumaczona treść Markdown
    title: str
    subtitle: Optional[str] = "Poradnik"
    author: Optional[str] = "FOTZ Studio"
    toc_items: Optional[List[TocItem]] = None
    keywords_to_bold: Optional[List[str]] = None
    cover_url: Optional[str] = None
    infographic_urls: Optional[List[str]] = None
    logo_url: Optional[str] = None

class ZipRequest(BaseModel):
    pdf_content: str
    title: str
    subtitle: Optional[str] = "Poradnik"
    author: Optional[str] = "FOTZ Studio"
    toc_items: Optional[List[TocItem]] = None
    keywords_to_bold: Optional[List[str]] = None
    cover_url: Optional[str] = None
    mockup_url: Optional[str] = None
    infographic_urls: Optional[List[str]] = None
    logo_url: Optional[str] = None
    blog_post: Optional[str] = None
    shop_description: Optional[str] = None

# =============================================================================
# FUNKCJE FORMATOWANIA FOTZ
# =============================================================================

# Lista nazw własnych (zawsze z wielkiej litery)
PROPER_NOUNS = [
    "Notion", "Trello", "Asana", "Google", "Zapier", "YouTube",
    "Instagram", "TikTok", "Facebook", "LinkedIn", "Twitter",
    "Excel", "Tableau", "PowerBI", "Buffer", "HubSpot",
    "ICE", "EVP", "SOP", "AI", "API", "DeepL", "FOTZ"
]

def standardize_titles(content: str) -> str:
    """
    Standaryzuje tytuły zgodnie z zasadami polszczyzny.
    Tylko pierwsze słowo z wielkiej litery (wyjątek: nazwy własne).
    """
    def process_title(match):
        prefix = match.group(1)
        title = match.group(2)
        
        words = title.split()
        if not words:
            return match.group(0)
        
        result = [words[0].capitalize()]
        
        for word in words[1:]:
            is_proper = any(pn.lower() == word.lower() for pn in PROPER_NOUNS)
            if is_proper:
                for pn in PROPER_NOUNS:
                    if pn.lower() == word.lower():
                        result.append(pn)
                        break
            else:
                result.append(word.lower())
        
        return f"{prefix} {' '.join(result)}"
    
    pattern = r'^(#{2,4})\s+(.+)$'
    content = re.sub(pattern, process_title, content, flags=re.MULTILINE)
    
    return content


def apply_bold_keywords(content: str, keywords: List[str]) -> str:
    """
    Automatycznie pogrubia słowa kluczowe z polskimi końcówkami.
    """
    if not keywords:
        return content
    
    for keyword in keywords:
        # Regex uwzględniający polskie końcówki (do 6 znaków po rdzeniu)
        pattern = rf'(?<!\*\*)({re.escape(keyword)}[a-ząćęłńóśźż]{{0,6}})(?!\*\*)'
        
        def replace_first_in_paragraph(text):
            paragraphs = text.split('\n\n')
            result = []
            for para in paragraphs:
                para = re.sub(pattern, r'**\1**', para, count=1, flags=re.IGNORECASE)
                result.append(para)
            return '\n\n'.join(result)
        
        content = replace_first_in_paragraph(content)
    
    return content


def process_content(content: str, keywords: Optional[List[str]] = None) -> str:
    """
    Główna funkcja przetwarzająca treść - stosuje wszystkie zasady FOTZ.
    """
    # 1. Standaryzacja tytułów
    content = standardize_titles(content)
    
    # 2. Pogrubienie słów kluczowych
    if keywords:
        content = apply_bold_keywords(content, keywords)
    
    return content

# =============================================================================
# GENEROWANIE CSS
# =============================================================================

def get_fotz_css() -> str:
    """Zwraca CSS zgodny z brandingiem FOTZ."""
    return f'''
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');

@page {{
    size: A4;
    margin: 2cm 2cm 2.5cm 2cm;
    @bottom-center {{
        content: counter(page);
        font-family: 'Open Sans', sans-serif;
        font-size: 10pt;
        color: #666;
    }}
}}

body {{
    font-family: 'Open Sans', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
    text-align: justify;
}}

h1 {{
    font-size: 24pt;
    color: {BRANDING["primary_color"]};
    margin-top: 40pt;
    margin-bottom: 20pt;
    page-break-before: always;
}}

h2 {{
    font-size: 18pt;
    color: {BRANDING["primary_color"]};
    margin-top: 30pt;
    margin-bottom: 15pt;
    border-bottom: 2px solid {BRANDING["primary_color"]};
    padding-bottom: 5pt;
}}

h3 {{
    font-size: 14pt;
    color: {BRANDING["secondary_color"]};
    margin-top: 20pt;
    margin-bottom: 10pt;
}}

h4 {{
    font-size: 12pt;
    color: {BRANDING["secondary_color"]};
    font-weight: bold;
    margin-top: 15pt;
    margin-bottom: 8pt;
}}

p {{
    margin-bottom: 10pt;
    text-align: justify;
}}

strong {{
    color: {BRANDING["secondary_color"]};
}}

a {{
    color: {BRANDING["secondary_color"]};
    text-decoration: underline;
}}

blockquote {{
    border-left: 4px solid {BRANDING["primary_color"]};
    margin: 20pt 0;
    padding: 15pt 20pt;
    background-color: #f9f9f9;
    font-style: italic;
    color: {BRANDING["secondary_color"]};
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin: 15pt 0;
    font-size: 10pt;
}}

th {{
    background-color: {BRANDING["primary_color"]};
    color: white;
    padding: 10pt 8pt;
    text-align: left;
    font-weight: bold;
}}

td {{
    padding: 8pt;
    border: 1px solid #ddd;
}}

tr:nth-child(even) {{
    background-color: #f5f5f5;
}}

ul, ol {{
    margin-left: 20pt;
    margin-bottom: 10pt;
}}

li {{
    margin-bottom: 5pt;
}}

.toc {{
    margin: 30pt 0;
}}

.toc-item {{
    display: flex;
    justify-content: space-between;
    padding: 8pt 0;
    border-bottom: 1px dotted #ccc;
}}

.toc-title {{
    color: {BRANDING["secondary_color"]};
}}

.toc-page {{
    color: #666;
}}
'''

# =============================================================================
# GENEROWANIE PDF
# =============================================================================

def download_image(url: str, temp_dir: str, filename: str) -> Optional[str]:
    """Pobiera obraz z URL i zapisuje lokalnie."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        return filepath
    except Exception as e:
        print(f"Błąd pobierania obrazu {url}: {e}")
        return None


def create_full_page_image_pdf(image_path: str, output_path: str) -> str:
    """Tworzy PDF z obrazem na całą stronę A4."""
    c = canvas.Canvas(output_path, pagesize=A4)
    
    img = Image.open(image_path)
    img_width, img_height = img.size
    
    scale_w = PAGE_WIDTH / img_width
    scale_h = PAGE_HEIGHT / img_height
    scale = max(scale_w, scale_h)
    
    new_width = img_width * scale
    new_height = img_height * scale
    
    x = (PAGE_WIDTH - new_width) / 2
    y = (PAGE_HEIGHT - new_height) / 2
    
    c.drawImage(image_path, x, y, new_width, new_height)
    c.save()
    
    return output_path


def generate_toc_html(toc_items: List[TocItem]) -> str:
    """Generuje HTML spisu treści."""
    html = f'''
    <h2 style="color: {BRANDING["primary_color"]}; border-bottom: 2px solid {BRANDING["primary_color"]}; padding-bottom: 10px; page-break-before: avoid;">
        SPIS TREŚCI
    </h2>
    <div class="toc">
    '''
    
    for item in toc_items:
        html += f'''
        <div class="toc-item">
            <span class="toc-title">{item.title}</span>
            <span class="toc-page">{item.page}</span>
        </div>
        '''
    
    html += '</div>'
    return html


def generate_pdf_from_content(request: PdfRequest, temp_dir: str) -> bytes:
    """Generuje PDF z przetłumaczonej treści."""
    
    # 1. Przetwórz treść (formatowanie FOTZ)
    processed_content = process_content(request.content, request.keywords_to_bold)
    
    # 2. Konwertuj Markdown na HTML
    content_html = markdown.markdown(processed_content, extensions=['tables', 'fenced_code'])
    
    # 3. Generuj spis treści
    toc_html = ""
    if request.toc_items:
        toc_html = generate_toc_html(request.toc_items)
    
    # 4. Pobierz logo jeśli podano URL
    logo_html = ""
    if request.logo_url:
        logo_path = download_image(request.logo_url, temp_dir, "logo.png")
        if logo_path:
            logo_html = f'''
            <div style="page-break-before: always; text-align: center; padding-top: 200pt;">
                <img src="file://{logo_path}" style="width: 150pt; height: auto;" />
                <p style="margin-top: 30pt; font-size: 14pt; color: {BRANDING["secondary_color"]};">
                    FOTZ Studio
                </p>
                <p><a href="https://fotz.pl" style="color: {BRANDING["secondary_color"]};">fotz.pl</a></p>
            </div>
            '''
    
    # 5. Stwórz pełny dokument HTML
    full_html = f'''<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>{request.title}</title>
    <style>{get_fotz_css()}</style>
</head>
<body>
{toc_html}
{content_html}
{logo_html}
</body>
</html>'''
    
    # 6. Zapisz HTML do pliku tymczasowego
    html_path = os.path.join(temp_dir, "content.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    # 7. Konwertuj HTML na PDF (treść)
    content_pdf_path = os.path.join(temp_dir, "content.pdf")
    HTML(filename=html_path).write_pdf(content_pdf_path)
    
    # 8. Połącz wszystkie PDFy
    merger = PdfMerger()
    
    # Okładka (jeśli podano)
    if request.cover_url:
        cover_path = download_image(request.cover_url, temp_dir, "cover.png")
        if cover_path:
            cover_pdf_path = os.path.join(temp_dir, "cover.pdf")
            create_full_page_image_pdf(cover_path, cover_pdf_path)
            merger.append(cover_pdf_path)
    
    # Treść
    merger.append(content_pdf_path)
    
    # Infografiki (jeśli podano)
    if request.infographic_urls:
        for i, url in enumerate(request.infographic_urls):
            inf_path = download_image(url, temp_dir, f"infographic_{i}.png")
            if inf_path:
                inf_pdf_path = os.path.join(temp_dir, f"infographic_{i}.pdf")
                create_full_page_image_pdf(inf_path, inf_pdf_path)
                merger.append(inf_pdf_path)
    
    # 9. Zapisz finalny PDF
    final_pdf_path = os.path.join(temp_dir, "final.pdf")
    merger.write(final_pdf_path)
    merger.close()
    
    # 10. Wczytaj i zwróć jako bytes
    with open(final_pdf_path, 'rb') as f:
        return f.read()

# =============================================================================
# ENDPOINTY API
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "FOTZ PDF Microservice", "version": "1.0.0"}


@app.post("/generate-pdf")
async def generate_pdf(request: PdfRequest):
    """
    Generuje PDF z przetłumaczonej treści.
    
    Przyjmuje:
    - content: Przetłumaczona treść w formacie Markdown
    - title: Tytuł ebooka
    - toc_items: Lista pozycji spisu treści (opcjonalnie)
    - keywords_to_bold: Lista słów do pogrubienia (opcjonalnie)
    - cover_url: URL do okładki (opcjonalnie)
    - infographic_urls: Lista URL do infografik (opcjonalnie)
    - logo_url: URL do logo (opcjonalnie)
    
    Zwraca: Plik PDF
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_bytes = generate_pdf_from_content(request, temp_dir)
            
            # Generuj nazwę pliku
            safe_title = re.sub(r'[^\w\s-]', '', request.title).replace(' ', '_')
            filename = f"{safe_title}.pdf"
            
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd generowania PDF: {str(e)}")


@app.post("/generate-zip")
async def generate_zip(request: ZipRequest):
    """
    Generuje kompletny pakiet ZIP z wszystkimi plikami.
    
    Zwraca: Archiwum ZIP zawierające PDF, grafiki i treści marketingowe.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                
                # 1. Generuj PDF
                pdf_request = PdfRequest(
                    content=request.pdf_content,
                    title=request.title,
                    subtitle=request.subtitle,
                    author=request.author,
                    toc_items=request.toc_items,
                    keywords_to_bold=request.keywords_to_bold,
                    cover_url=request.cover_url,
                    infographic_urls=request.infographic_urls,
                    logo_url=request.logo_url
                )
                pdf_bytes = generate_pdf_from_content(pdf_request, temp_dir)
                
                safe_title = re.sub(r'[^\w\s-]', '', request.title).replace(' ', '_')
                zipf.writestr(f"{safe_title}.pdf", pdf_bytes)
                
                # 2. Dodaj okładkę
                if request.cover_url:
                    cover_path = download_image(request.cover_url, temp_dir, "cover_dl.png")
                    if cover_path:
                        with open(cover_path, 'rb') as f:
                            zipf.writestr("cover_a4.png", f.read())
                
                # 3. Dodaj mockup
                if request.mockup_url:
                    mockup_path = download_image(request.mockup_url, temp_dir, "mockup_dl.png")
                    if mockup_path:
                        with open(mockup_path, 'rb') as f:
                            zipf.writestr("mockup_tablet.png", f.read())
                
                # 4. Dodaj infografiki
                if request.infographic_urls:
                    for i, url in enumerate(request.infographic_urls, 1):
                        inf_path = download_image(url, temp_dir, f"inf_{i}_dl.png")
                        if inf_path:
                            with open(inf_path, 'rb') as f:
                                zipf.writestr(f"infographic_{i}.png", f.read())
                
                # 5. Dodaj blog post
                if request.blog_post:
                    zipf.writestr("blog_post.md", request.blog_post.encode('utf-8'))
                
                # 6. Dodaj opis sklepu
                if request.shop_description:
                    zipf.writestr("opis_sklepu.md", request.shop_description.encode('utf-8'))
                
                # 7. Dodaj logo
                if request.logo_url:
                    logo_path = download_image(request.logo_url, temp_dir, "logo_dl.png")
                    if logo_path:
                        with open(logo_path, 'rb') as f:
                            zipf.writestr("logo_fotz.png", f.read())
            
            zip_buffer.seek(0)
            
            filename = f"{safe_title}_FOTZ.zip"
            
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd generowania ZIP: {str(e)}")


# =============================================================================
# URUCHOMIENIE
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
