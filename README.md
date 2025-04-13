# Quoridor Bot ♟️

<p align="center">
  <!-- PLACEHOLDER: Replace with a screenshot or GIF of your web interface! -->
  <!-- Create a 'docs' folder, add image/gif, update path below -->
  <img src="./docs/quoridor_demo.png" alt="Quoridor Bot Gameplay" width="700"/>
</p>

Play the strategic board game Quoridor against an algorithmic AI opponent through a web interface powered by Flask. This project implements the core Quoridor game logic and pits a human player against a bot capable of searching for optimal moves.

---

## 🌟 Features

*   **Web-Based Interface:** Play the game visually in your web browser using Flask and standard HTML/CSS/JavaScript.
*   **Human vs. AI:** Challenge an algorithmic bot opponent (`quoridor_bot.py`).
*   **Configurable Bot Difficulty:** Adjust the bot's search depth (`BOT_SEARCH_DEPTH` in `app.py`) to change its playing strength and response time.
*   **Core Quoridor Logic:** Implements standard Quoridor rules for pawn movement, wall placement, win conditions, and validation (`quoridor_logic.py`).
*   **Valid Move Enforcement:** The backend validates all moves (both human and bot) according to game rules.
*   **Clear Game State Display:** The UI reflects the current pawn positions, remaining walls, placed walls, and whose turn it is.
*   **Real-time(ish) Gameplay:** Uses HTTP requests and responses (potentially polling) to manage turns between the human player and the server-side bot.
*   **Informative Logging:** Server-side console provides detailed logs of game state, moves attempted, and bot decisions.

---

## 💡 How It Works

1.  **Server Start:** The Flask application (`app.py`) is launched, initializing the game logic and the Quoridor Bot.
2.  **Client Connect:** The user opens the web interface in their browser, which loads the initial HTML (`templates/index.html`) and associated static assets (CSS/JS).
3.  **Start Game:** The user clicks the "Start Game" button (or similar UI element). This sends a request to the `/start_game` endpoint on the Flask server.
4.  **Game Initialization:** The server resets the `QuoridorGame` instance. If the Bot (Player 1) starts first, the server runs `run_bot_turn()` to calculate and make the bot's initial move. The initial game state is sent back to the client.
5.  **Human Turn:**
    *   The client UI displays the board and indicates it's the human's turn (Player 2).
    *   The human interacts with the UI to decide on a move (e.g., `move e2`, `wall e5h`).
    *   The client sends the chosen move string via a POST request to the `/make_human_move` endpoint.
6.  **Server Processing (Human Move):**
    *   The server receives the move string.
    *   It validates the move using `game.make_move()`.
    *   If **invalid**, an error response is sent back to the client.
    *   If **valid**:
        *   The game state is updated.
        *   The server checks if the human move resulted in a win.
        *   If the game continues, the server calls `run_bot_turn()`.
7.  **Server Processing (Bot Turn):**
    *   `run_bot_turn()` calls `bot.find_best_move()` (which likely uses an algorithm like Minimax or Alpha-Beta Pruning up to `BOT_SEARCH_DEPTH`).
    *   The server attempts to make the bot's chosen move using `game.make_move()`.
    *   It checks if the bot's move resulted in a win.
8.  **State Update:** The server sends the final game state (after both human and potentially bot moves) back to the client in the response to `/make_human_move`.
9.  **UI Update:** The client's JavaScript receives the updated game state and redraws the board/updates status messages. *(The `/game_state` endpoint suggests the client might also poll periodically for updates, though this isn't explicitly shown in `app.py`'s primary turn logic).*
10. **Game End:** When a win condition is met, the `game_active` flag is set to `False`, and the winner is indicated in the game state sent to the client.

---

## 🛠️ Tech Stack

*   **Backend:**
    *   Python 3
    *   Flask (Web Framework)
*   **Game Logic:**
    *   `quoridor_logic.py` (Custom module for game rules)
    *   `quoridor_bot.py` (Custom module for AI opponent logic)
*   **Frontend:**
    *   HTML5 (served via Flask Templates)
    *   CSS3 (in `static/` folder)
    *   JavaScript (in `static/` folder, handles UI updates and communication with Flask backend)
*   **(Optional/Implied):**
    *   Ollama Interface (`ollama_interface.py` - presence suggests potential integration, though not directly used in `app.py` logic shown)

---

## 🚀 Getting Started

1.  **Prerequisites:**
    *   Python 3 installed ([https://www.python.org/](https://www.python.org/))
    *   `pip` (Python package installer, usually comes with Python)
    *   Git (optional, for cloning)
2.  **Clone the Repository (or download files):**
    ```bash
    git clone https://github.com/twykex/Quoridor_Bot.git
    cd Quoridor_Bot
    ```
3.  **Create and Activate a Virtual Environment (Recommended):**
    ```bash
    # Create venv (might be python3 instead of python on some systems)
    python -m venv venv
    # Activate venv
    # Windows: .\venv\Scripts\activate
    # macOS/Linux: source venv/bin/activate
    ```
4.  **Install Dependencies:**
    *   *You need to create a `requirements.txt` file.* Based on `app.py`, it likely only needs Flask for now. Create `requirements.txt` with the content:
        ```
        Flask
        ```
    *   Then install:
        ```bash
        pip install -r requirements.txt
        ```
5.  **Configure Bot (Optional):**
    *   Open `app.py` and adjust `BOT_SEARCH_DEPTH` if desired (higher = stronger but slower).
6.  **Run the Application:**
    ```bash
    python app.py
    ```
    You should see output like `Starting Flask server...` and `* Running on http://0.0.0.0:25565`.
7.  **Play:**
    *   Open your web browser and go to `http://localhost:25565` (or your machine's IP address on port 25565 if accessing from another device on the network).
    *   Click the "Start Game" button and play against the bot!

---

## ▶️ How to Play

*   The game board is displayed. You are Player 2 (usually represented by the pawn starting at the bottom). The Bot is Player 1.
*   The goal is to reach the opposite side of the board before your opponent does.
*   On your turn, you can either:
    *   **Move your pawn:** One square orthogonally (up, down, left, right). Pawns cannot jump over walls but can jump over *one* adjacent pawn. Enter moves like `move e8`.
    *   **Place a wall:** Place a wall segment (which covers two squares horizontally or vertically) to block movement. You have a limited number of walls (usually 10). Enter wall placements like `wall e5h` (horizontal at row 5 between columns e and f) or `wall d4v` (vertical at column d between rows 4 and 5).
*   **Wall Rules:**
    *   Walls cannot overlap existing walls.
    *   You cannot place a wall that completely blocks *all* possible paths for *either* player to reach their goal row.
*   The web interface will provide input methods for making your move. Follow the on-screen prompts.
