
## Project Description

This is about Flask-based minigame platform with two distinct roles. **Game hosts** register and log in to create and customize luck-based minigames (Lucky Wheel, Lucky Cards, Lucky Balls), configure prizes and probabilities, and distribute unique per-participant codes alongside the game URL. **Participants** visit the shared URL, enter their personal code to unlock the game, play once, and see their result. Hosts can later export a CSV/report mapping each participant code to the system-recorded result, allowing them to cross-check against any results participants self-report.

---

## User Stories

### Game Host

**1. Account & authentication**
As a game host, I want to register and log in to the platform, so that my games and participant data are private and only accessible to me.

**2. Create & configure a game**
As a game host, I want to create a new game by choosing a game type (Lucky Wheel, Lucky Cards, Lucky Balls), defining prizes with labels, images, and probability weights, so that the game is fully tailored before I share it.

**3. Visual customization**
As a game host, I want to customize the game's colors and appearance, so that it fits my event or campaign branding.

**4. Generate participant codes**
As a game host, I want to generate a batch of unique one-time codes (e.g. `PLAYER-A3X9`) tied to my game, so that I can distribute one code per participant and control exactly who can play.

**5. Share the game link**
As a game host, I want to receive a shareable game URL (e.g. `abc.com/play/<uuid>`) after creating a game, so that I can send it alongside each participant's code via any channel (email, WhatsApp, etc.).

**6. Export results**
As a game host, I want to export a CSV file containing each participant's code, name (if collected), and their system-recorded result, so that I can verify the results players report to me are accurate.

**7. Game dashboard**
As a game host, I want to see a dashboard listing all my games with their status (active/inactive) and how many participants have played, so that I can monitor engagement at a glance.

---

### Participant

**8. Code-gated entry**
As a participant, I want to visit the game URL and enter my personal code to unlock the game, so that only I can use my code and play on my behalf.

**9. Single play enforcement**
As a participant, I want my code to be marked as used immediately after I play, so that the game cannot be replayed or tampered with after seeing the result.

**10. Result screen**
As a participant, I want to see a clear result screen after playing that shows my prize (image + label), so that I know what I won and can report or screenshot it for the host.

---

## CSS Framework: **Bootstrap 5**

Bootstrap is the right choice here because the platform has lots of form-heavy UI (prize config, code generation, exports) where Bootstrap's grid, form components, modals, and tables save significant time. It also has solid documentation and jQuery compatibility built-in, which aligns perfectly with your allowed stack.

---

## Pages

### Auth
| Page | URL | Description |
|---|---|---|
| Register | `/register` | Host sign-up form — username, email, password |
| Login | `/login` | Host login form |

### Host (requires login)
| Page | URL | Description |
|---|---|---|
| Dashboard | `/dashboard` | Lists all the host's games with status, play count, quick actions |
| Create Game | `/games/create` | Step-by-step form — pick game type, configure prizes, upload images, set weights, customize appearance |
| Manage Game | `/games/<uuid>` | View a single game's details, active/inactive toggle, copy shareable link, regenerate codes |
| Participant Codes | `/games/<uuid>/codes` | View all generated codes, which have been played, export CSV of codes + results |

### Play (public, no login)
| Page | URL | Description |
|---|---|---|
| Game Entry | `/play/<uuid>` | Participant enters their personal code to unlock the game |
| Game Screen | `/play/<uuid>/go` | The actual minigame renders here — wheel, cards, or balls |
| Result Screen | `/play/<uuid>/result` | Shows prize image + label after playing; code is marked used |

### Misc
| Page | URL | Description |
|---|---|---|
| 404 | `/404` | Friendly error page for invalid game UUIDs or expired codes |

### Flow

The platform has **9 pages** split cleanly across two roles:

**Host (login required) — 5 pages:** Register, Login, Dashboard, Create Game, Manage Game, Participant Codes

**Participant (public) — 3 pages:** Game Entry (code gate), Game Screen, Result Screen

**Misc — 1 page:** 404 for invalid UUIDs or already-used codes

The key design insight in the flow is that the host's `/games/<uuid>/codes` page and the participant's `/play/<uuid>` entry point are two separate windows into the same game record — the host sees all codes and results in aggregate, while each participant only ever sees their own single-use experience.