# Discordbot

Ett Python-projekt för en Discordbot. Botten är under uppbyggnad; `bot.py` är tänkt som startpunkt.

## Kom igång

1. Installera Python 3.10 eller senare.
2. Skapa och aktivera en virtuell miljö:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. Installera projektets beroenden när de har lagts till (till exempel från `requirements.txt`).
4. Lägg Discord-bottens token i en `.env`-fil. Lägg aldrig upp token eller andra hemligheter i Git.
5. Starta botten:

   ```bash
   python bot.py
   ```

## Konfiguration

Skapa en `.env`-fil i projektroten och ange bottens token, till exempel:

```dotenv
DISCORD_TOKEN=din-token-här
```

Läs in värdet i koden med en lämplig miljövariabelhanterare. `.env` ignoreras av Git.

## Utveckling

Lägg till installation och användning av botkommandon här när funktionerna är på plats. Beroenden kan dokumenteras i `requirements.txt`.
