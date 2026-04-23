Project Architecture Rules

- Backend uses Python + FastAPI
- ElevenLabs is the only voice provider
- Services must remain modular
- Business logic belongs in /services
- API routes stay lightweight
- Voice cloning must use ElevenLabs SDK
- All modules map to specs in /specs
- Avoid inline logic inside routes