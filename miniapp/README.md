# Telegram MiniApp - Selector de personajes

Mini app web para elegir personaje y enviar la selección al bot usando `Telegram.WebApp.sendData(...)`.

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

## Payload enviado al bot

```json
{
  "type": "select_character",
  "character": "sofia",
  "world": "realistic",
  "ts": 1730000000000
}
```
