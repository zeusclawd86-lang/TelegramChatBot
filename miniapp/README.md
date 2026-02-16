# Telegram MiniApp - Selector de personajes

Mini app web para elegir personaje (agrupado por `world type`) y enviar la selección al bot usando `Telegram.WebApp.sendData(...)`.

## Despliegue rápido

Sube esta carpeta a un hosting HTTPS (Vercel/Netlify/GitHub Pages).

Luego configura en el entorno del bot:

```bash
TELEGRAM_MINIAPP_URL=https://tu-dominio/miniapp/index.html
```

Y usa en Telegram:

```text
/miniapp
```

## Estructura de personajes (agrupada)

`characters.json` usa `worldTypes`:

```json
{
  "worldTypes": [
    {
      "id": "realistic",
      "label": "🌍 Realista",
      "characters": [
        { "id": "sofia", "name": "Sofia", "icon": "🔥", "short": "..." }
      ]
    }
  ]
}
```

## Payload enviado al bot

```json
{
  "type": "select_character_scenario",
  "character": "sofia",
  "world": "realistic",
  "scenario": "beach",
  "ts": 1730000000000
}
```
