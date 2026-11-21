# Application workflows

This document explains the main listener and collaboration journeys in MannKiDhun. The diagrams describe the current implementation and its boundaries, rather than future roadmap concepts.

## 1. Music discovery journey

```mermaid
flowchart TD
    Open["Open MannKiDhun"] --> Auth{"Signed in?"}
    Auth -->|"No"| SignIn["Sign up or sign in"]
    Auth -->|"Yes"| Assistant["Open Music Assistant"]
    SignIn --> Assistant
    Assistant --> Mode["Choose Match, Change, or Explore"]
    Mode --> Request["Type a request or use browser speech input"]
    Request --> Context["Optionally select a listening context"]
    Context --> Consent["Choose whether to use preferences or listening history"]
    Consent --> Submit["Submit request to Flask API"]
    Submit --> Parse["Parse and validate supported search intent"]
    Parse --> Rank["Filter and rank the curated catalogue"]
    Rank --> Matches{"Matching tracks available?"}
    Matches -->|"Yes"| Show["Show recommendations and catalogue-based reasons"]
    Matches -->|"No"| Alternatives["Explain the filter gap and offer catalogue alternatives"]
    Alternatives --> Show
    Show --> Play["Select and play a track"]
    Play --> Feedback["Optionally Like or select Not for me"]
    Feedback --> Adapt["Refresh remaining adaptive queue when applicable"]
```

### Modes

- **Match:** find catalogue tracks for the current or requested mood.
- **Change:** create a three-stage source mood → heuristic bridge → target mood journey.
- **Explore:** browse without a mood constraint while retaining explicit catalogue filters.

Change is a catalogue-ranking heuristic. It is not a validated psychological model.

## 2. Optional expression-based check-in

```mermaid
flowchart TD
    Start["Choose Find my expression"] --> Consent["Grant camera access and start the check"]
    Consent --> Capture["Capture five temporary frames"]
    Capture --> Request["Send frames to Flask /predict"]
    Request --> Quality["Validate frame format and quality"]
    Quality --> Enough{"Enough usable frames?"}
    Enough -->|"No"| Manual["Retry or select a mood manually"]
    Enough -->|"Yes"| Infer["MediaPipe / OpenCV processing and Keras inference"]
    Infer --> Combine["Aggregate predictions across frames"]
    Combine --> Reliable{"Sufficiently consistent?"}
    Reliable -->|"No"| Manual
    Reliable -->|"Yes"| Display["Display an expression estimate"]
    Display --> Accepted{"Listener confirms it?"}
    Accepted -->|"No"| Manual
    Accepted -->|"Yes"| Prefill["Prefill Match mode with confirmed mood"]
    Manual --> Discover["Continue with Music Assistant"]
    Prefill --> Discover
```

**Privacy boundary:** camera use is optional. Five frames are processed in request memory and are not written to disk by the expression endpoint. A model estimate is not a reliable measurement of inner emotional state; the listener must confirm it, and manual selection remains available.

## 3. Assistant request sequence

```mermaid
sequenceDiagram
    autonumber
    actor Listener
    participant Browser as React application
    participant API as Flask API
    participant Parser as Music Assistant
    participant AI as Optional intent provider
    participant Engine as Recommendation engine
    participant DB as SQLite

    Listener->>Browser: Enter a music request
    Browser->>API: POST /api/v1/assistant/chat
    API->>API: Validate session, payload and consent
    API->>Parser: Pass request and selected options

    opt Intent provider configured
        Parser->>AI: Send current text for structured intent
        AI-->>Parser: Return structured fields
    end

    Parser->>Parser: Validate provider intent or fall back to local rules
    Parser->>Engine: Pass normalized intent
    Engine->>DB: Read catalogue and permitted personalisation signals
    DB-->>Engine: Return tracks and selected signals
    Engine->>Engine: Apply filters, ranking and explanation rules
    Engine-->>API: Return catalogue-backed recommendations
    API-->>Browser: JSON response
    Browser-->>Listener: Render tracks and reasons
```

The optional provider does not receive camera frames, session credentials, or listening history. If it is not configured or cannot produce usable structured intent, local rule-based parsing is used.

## 4. Playlist collaboration and group listening

Playlist editing access and group listening rooms are separate features. Collaboration invitations control who can access or edit a playlist; a listening-room invitation controls participation in a temporary shared playback session.

```mermaid
flowchart TD
    Owner["Playlist owner"] --> Playlist["Create or open a playlist"]
    Playlist --> Share{"Choose a sharing action"}
    Share -->|"Publish"| Public["Mark playlist public"]
    Public --> Directory["Community directory and read-only public page"]
    Share -->|"Invite collaborator"| Invite["Create viewer or editor invitation"]
    Invite --> Expiry["Seven-day invitation link"]
    Expiry --> Guest["Guest signs in and accepts invitation"]
    Guest --> Role{"Assigned role"}
    Role -->|"Viewer"| Read["Read playlist; no edits"]
    Role -->|"Editor"| Edit["Add, remove, and reorder tracks"]
    Playlist --> Room["Owner creates group listening room"]
    Room --> Token["Create six-hour room link"]
    Token --> Join["Signed-in guests join with bearer link"]
    Join --> Poll["Participants poll shared state and recent presence"]
    Poll --> Version{"Playback update version current?"}
    Version -->|"Yes"| Sync["Accept new state and version"]
    Version -->|"No"| Conflict["Return conflict; refresh latest state"]
    Conflict --> Poll
    Sync --> Poll
    Room --> Close["Owner closes room or it expires"]
```

### Collaboration rules

- Public playlists are opt-in and read-only to visitors.
- Private playlist invitations expire after seven days and grant either viewer or editor access.
- Accepted collaborators are managed by the playlist owner; revoking an unused invite does not automatically remove an already accepted collaborator.
- Group listening rooms expire after six hours. Treat the room URL as a bearer secret.
- Guests must be signed in to join a room. Room state is synchronised through periodic polling and optimistic version checks, not WebSockets.

## 5. Playback and feedback lifecycle

```mermaid
flowchart TD
    Recommendation["Choose a catalogue recommendation"] --> Start["Start YouTube embed playback"]
    Start --> Record["Record play interaction where available"]
    Record --> Decision{"Listener provides feedback?"}
    Decision -->|"Like"| Positive["Record positive feedback"]
    Decision -->|"Not for me"| Negative["Record skip feedback"]
    Decision -->|"No feedback"| Continue["Continue listening"]
    Positive --> Consent{"History use enabled for ranking?"}
    Negative --> Consent
    Consent -->|"Yes"| Personalise["Use permitted interaction signal in ranking"]
    Consent -->|"No"| Ignore["Do not use history-derived signals for this request"]
    Personalise --> Queue["Re-rank remaining adaptive queue when applicable"]
    Ignore --> Queue
    Continue --> Queue
```

Feedback is stored against the signed-in account. History-derived recommendation signals are used only when the listener explicitly enables history use for the request. The global queue is application-managed; audio delivery remains subject to YouTube and browser restrictions.
