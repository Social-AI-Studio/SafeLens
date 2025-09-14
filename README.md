# SafeLens: Hateful Video Moderation

## Demo Video

- [YouTube](https://youtu.be/B1dYceLSnXA)

## Repo Guide


**Repo Layout**

- `web/` — Website/UI for the demo and docs. Everything related to the web frontend shown in the video demo lives here.
- `auth-service/` — Authentication service (API and logic). Everything related to auth lives here. (required to setup the web demo)

**Project Tree**

```
.
├── web/               # Website/UI (backend & frontend)
│   ├── frontend/      # frontend
│   └── ...            # backend
├── auth-service/      # Authentication service
│   ├── src/
│   └── ...
├── README.md
```

## Setup

1. Setup `auth-service/` by following `auth-service/README.md`
1. Setup `web/` by following `web/README.md` and `web/frontend/README.md`
