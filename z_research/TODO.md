# TODO

> Última actualización: 2026-01-31

---

## 🎯 Fase 1 - Core (2-3 semanas)

### Detección de Imágenes (PRIORIDAD ALTA)
- [ ] Implementar Vision API (GPT-4V o Grok Vision)
- [ ] Handler para imágenes en `src/handlers.py`
- [ ] Modificar `LangChainAgent` para input de imágenes
- **Ventaja**: Lucid Dreams NO tiene esto
- **Ref**: `research/lucid_dreams.md:292`

### Formato Narrativo
- [ ] Modificar prompt para usar `**texto**` en tercera persona
- [ ] Agregar ejemplos al system prompt
- **Ref**: `research/lucid_dreams.md:18-32`

### Mensajes Proactivos
- [ ] Timeout 1 minuto → enviar mensaje del personaje
- [ ] Ejemplos: "¿Sigues ahí?", "¿Qué estás haciendo?"
- **Ref**: `research/lucid_dreams.md:125-128`

### Checkpoints
- [ ] Comando `/checkpoint` - guardar estado conversación
- [ ] Free: 3 max, Premium: ilimitado
- [ ] Campos: `user_id`, `timestamp`, `context`, `history`, `image_counter`
- **Ref**: `research/lucid_dreams.md:303`

---

## 💰 Fase 2 - Monetización (3-4 semanas)

### Sistema de Energía
- [ ] Free: 50 msgs/día, Basic: 100, Pro: ilimitado
- [ ] Agregar `energy` a `UserContext` (`src/context.py`)
- [ ] Crear `EnergyManager` en `src/energy.py`
- [ ] Regeneración: +50 cada 24h
- **Ref**: `research/lucid_dreams.md:163-165`

### Moneda Virtual
- [ ] **Stars (⭐)**: pago real (Telegram Stars API)
- [ ] **Gems (💎)**: recompensas/logros
- [ ] DB: SQLite o JSON simple
- **Ref**: `research/lucid_dreams.md:50-52`

### Suscripciones
- [ ] **Basic** ($4.99/mes): 100 msgs/día, img cada 5 msgs
- [ ] **Pro** ($9.99/mes): ilimitado, img cada 3 msgs
- [ ] **Elite** ($19.99/mes): img por msg, modelos avanzados, personajes premium
- [ ] Integrar Telegram Payments o Stripe
- **Ref**: `research/lucid_dreams.md:165-168`

### Paywall
- [ ] Blur en imágenes NSFW para free users
- [ ] Badge "Premium to unlock"
- **Ref**: `research/lucid_dreams.md:100-101`

### Tienda
- [ ] Comando `/store` con inline keyboard
- [ ] Mostrar paquetes Stars, Gems, suscripciones
- **Ref**: `research/lucid_dreams.md:108-115`

---

## 🚀 Fase 3 - Growth (4+ semanas)

### Afiliados
- [ ] `/affiliate` - código único por usuario
- [ ] Recompensas: 50 gems/registro, 100 gems si compra, 5% comisión
- **Ref**: `research/lucid_dreams.md:313`

### Multi-idioma
- [ ] Auto-detectar idioma del usuario
- [ ] Guardar en contexto
- [ ] Soportar: ES, EN, PT, FR, DE, JP
- **Ref**: `research/lucid_dreams.md:308`

### Marketplace Personajes
- [ ] Personajes premium: 99 gems c/u
- [ ] Categorías: Anime, Celebrities, Fantasy, Históricos
- [ ] Cada uno: imagen ref (IP Adapter) + personalidad única
- **Ref**: `research/lucid_dreams.md:113`

### Analytics
- [ ] KPIs: DAU, Retention (D1/D7/D30), Conversion, ARPU, Churn
- [ ] Tools: LangSmith (ya hay) + Mixpanel/Amplitude
- [ ] Eventos: `user_registered`, `first_message`, `image_generated`, `energy_depleted`, `subscription_*`

---

## 🔧 Tech

- [ ] Separar lógica menus → `src/menu_adapter.py` (actualmente acoplado en `handlers.py:23-29`)
- [ ] Migrar de memoria a DB: SQLite/PostgreSQL/Redis (`src/context.py`)
- [ ] Tests unitarios con pytest (coverage >80%)
- [ ] Mejorar logging: ERROR/WARNING/INFO/DEBUG + alertas (tasa error >5%, latencia >10s)

---

## 🎨 UX

- [ ] `/help`, `/stats`, `/reset`, `/settings`, `/feedback`
- [ ] Doble imagen inicial: inmediata + 10s después (reduce bounce) - `src/menus.py`
- [ ] Typing indicators con delays (Free: 3-5s, Premium: 1-2s)

---

## 📚 Docs

- [ ] Landing page: Next.js + Tailwind
- [ ] Actualizar README.md con monetización
- [ ] ARCHITECTURE.md con diagramas

---

## 🔐 Seguridad

- [ ] Age verification +18
- [ ] GDPR: `/export_data`, `/delete_account`, privacy policy
- [ ] Rate limiting anti-spam

---

## 📊 Objetivos Q1 2026

- [ ] 1,000 usuarios, 100 DAU, retention D7 >20%
- [ ] 50 suscriptores, MRR $500, conversion 5%
- [ ] 50 msgs/usuario, 10 imgs/usuario, 80% satisfacción

---

## 💡 Backlog

- Gamificación: logros, XP, daily rewards
- Social: compartir convos, leaderboard, Discord
- Integraciones: WhatsApp, Discord, webapp, mobile app
- AI avanzado: TTS, STT, video gen, RAG memory

---

## ✅ Completado

**2026-01-31**
- Sistema retry orchestrator (3 intentos)
- Fallback cuando LLM vacío
- Análisis Lucid Dreams completo
- Estrategia monetización documentada

**2026-01-22 - 30**
- Grok API + LangSmith
- Refactor arquitectura en capas
- Lógica imágenes centralizada
- Terminal chat mode
- README + diagramas
- `.cursor/rules`
