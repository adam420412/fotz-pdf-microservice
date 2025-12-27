# FOTZ PDF Microservice

Mikroserwis do generowania profesjonalnych PDF dla FOTZ Ebook Factory.

## Funkcje

- **Generowanie PDF** z przetłumaczonej treści Markdown
- **Formatowanie FOTZ** - standaryzacja tytułów, pogrubienia z polskimi końcówkami
- **Integracja grafik** - okładka, infografiki na całą stronę
- **Pakowanie ZIP** - kompletny pakiet z PDF, grafikami i treściami marketingowymi

## Endpointy API

### `GET /health`
Health check - sprawdza czy serwis działa.

### `POST /generate-pdf`
Generuje PDF z przetłumaczonej treści.

**Request Body:**
```json
{
  "content": "# Tytuł\n\nTreść ebooka w Markdown...",
  "title": "Zbuduj swoją maszynę do tworzenia treści",
  "subtitle": "Poradnik",
  "author": "FOTZ Studio",
  "toc_items": [
    {"title": "Wprowadzenie", "page": 3},
    {"title": "Część 1: Budowanie banku pomysłów", "page": 5}
  ],
  "keywords_to_bold": ["treści", "system", "kalendarz"],
  "cover_url": "https://example.com/cover.png",
  "infographic_urls": [
    "https://example.com/infographic1.png",
    "https://example.com/infographic2.png"
  ],
  "logo_url": "https://example.com/logo.png"
}
```

**Response:** Plik PDF

### `POST /generate-zip`
Generuje kompletny pakiet ZIP.

**Request Body:** Jak wyżej, plus:
```json
{
  "mockup_url": "https://example.com/mockup.png",
  "blog_post": "# Post na bloga\n\nTreść...",
  "shop_description": "# Opis produktu\n\nTreść..."
}
```

**Response:** Archiwum ZIP

## Wdrożenie na Railway

### Opcja 1: Przez GitHub

1. Stwórz nowe repozytorium na GitHub
2. Wgraj wszystkie pliki z tego folderu
3. W Railway: New Project → Deploy from GitHub repo
4. Wybierz repozytorium
5. Railway automatycznie wykryje Dockerfile i zdeployuje

### Opcja 2: Przez Railway CLI

```bash
# Zainstaluj Railway CLI
npm install -g @railway/cli

# Zaloguj się
railway login

# Stwórz nowy projekt
railway init

# Wdróż
railway up
```

### Opcja 3: Przez Railway Dashboard

1. Idź do https://railway.app/new
2. Wybierz "Deploy from GitHub repo" lub "Empty Project"
3. Jeśli Empty Project: Add Service → Docker Image
4. Wgraj pliki lub połącz z repo

## Konfiguracja

Serwis automatycznie używa portu z zmiennej środowiskowej `PORT` (ustawianej przez Railway).

## Koszty Railway

- **Hobby Plan:** $5/miesiąc, wystarczający dla tego mikroserwisu
- **Zużycie:** ~$2-5/miesiąc przy umiarkowanym użyciu

## Integracja z Lovable

W Lovable, wywołuj endpointy przez fetch:

```javascript
const response = await fetch('https://your-railway-url.railway.app/generate-pdf', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    content: translatedContent,
    title: 'Tytuł ebooka',
    // ... pozostałe pola
  }),
});

const pdfBlob = await response.blob();
// Pobierz lub wyświetl PDF
```

## Testowanie lokalne

```bash
# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom serwer
python app.py

# Serwer dostępny na http://localhost:8000
# Dokumentacja API: http://localhost:8000/docs
```

## Autor

FOTZ Studio - fotz.pl
