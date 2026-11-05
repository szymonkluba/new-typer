from datetime import date

DEFAULT_LANG = "pl"
SUPPORTED_LANGS = ("pl", "en")

POLISH_MONTHS = {
    1: "sty",
    2: "lut",
    3: "mar",
    4: "kwi",
    5: "maj",
    6: "cze",
    7: "lip",
    8: "sie",
    9: "wrz",
    10: "paź",
    11: "lis",
    12: "gru",
}

ENGLISH_MONTHS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "pl": {
        "site_subtitle": "Rynek Prognostyczny Skoków Narciarskich",
        # Navbar
        "nav_competitions": "Konkursy",
        "nav_ranking": "Ranking",
        "nav_my_bets": "Moje Typy",
        "nav_login": "Zaloguj",
        "nav_register": "Rejestracja",
        "nav_logout": "Wyloguj",
        # Homepage
        "title_home": "Strona główna",
        "hero_tagline": "Typuj podium w skokach narciarskich i rywalizuj ze znajomymi!",
        "hero_join": "Dołącz teraz",
        "top_players": "Najlepsi gracze",
        "upcoming_competitions": "Nadchodzące konkursy",
        "view_all_competitions": "Zobacz wszystkie konkursy",
        "no_upcoming": "Brak nadchodzących konkursów",
        "no_upcoming_detail": "Wróć później lub poczekaj na pobranie nowych wydarzeń z FIS.",
        # Table headers (shared)
        "th_rank": "Pozycja",
        "th_player": "Gracz",
        "th_points": "Punkty",
        "th_athlete": "Zawodnik",
        "th_nation": "Kraj",
        "th_competition": "Konkurs",
        "th_date": "Data",
        "th_position": "Miejsce",
        # Error page
        "title_error": "Błąd",
        "back_to_home": "Powrót na stronę główną",
        # Auth
        "title_login": "Logowanie",
        "title_register": "Rejestracja",
        "label_username": "Nazwa użytkownika",
        "label_password": "Hasło",
        "label_password_confirm": "Potwierdź hasło",
        "btn_login": "Zaloguj się",
        "btn_register": "Zarejestruj się",
        "no_account": "Nie masz konta?",
        "have_account": "Masz już konto?",
        # Auth errors
        "err_username_short": "Nazwa użytkownika musi mieć co najmniej 3 znaki.",
        "err_password_short": "Hasło musi mieć co najmniej 6 znaków.",
        "err_password_mismatch": "Hasła nie są zgodne.",
        "err_username_taken": "Nazwa użytkownika jest już zajęta.",
        "err_invalid_credentials": "Nieprawidłowa nazwa użytkownika lub hasło.",
        # Competitions
        "title_competitions": "Konkursy",
        "tab_upcoming": "Nadchodzące",
        "tab_completed": "Zakończone",
        "tab_all": "Wszystkie",
        "no_competitions": "Nie znaleziono konkursów.",
        "err_competition_not_found": "Nie znaleziono konkursu.",
        # Competition detail
        "place_your_bet": "Postaw swój typ",
        "place_1st": "1. miejsce",
        "place_2nd": "2. miejsce",
        "place_3rd": "3. miejsce",
        "placeholder_athlete": "Nazwa zawodnika",
        "btn_place_bet": "Postaw typ",
        "btn_update_bet": "Zmień typ",
        "login_to_bet": "aby postawić typ!",
        "your_current_bet": "Twój aktualny typ",
        "betting_closed": "Typowanie zamknięte — konkurs już się rozpoczął.",
        "results": "Wyniki",
        # My bets
        "title_my_bets": "Moje Typy",
        "pending": "Oczekuje",
        "no_bets_yet": "Nie postawiłeś jeszcze żadnych typów.",
        "browse_competitions": "Przeglądaj konkursy",
        "to_get_started": "aby zacząć!",
        # Ranking
        "title_ranking": "Ranking",
        "title_leaderboard": "Tabela liderów",
        "no_players_yet": "Brak graczy.",
        "and_start_betting": "i zacznij typować!",
    },
    "en": {
        "site_subtitle": "Ski Jumping Prediction Market",
        # Navbar
        "nav_competitions": "Competitions",
        "nav_ranking": "Ranking",
        "nav_my_bets": "My Bets",
        "nav_login": "Login",
        "nav_register": "Register",
        "nav_logout": "Logout",
        # Homepage
        "title_home": "Home",
        "hero_tagline": "Predict ski jumping podiums and compete with your friends!",
        "hero_join": "Join Now",
        "top_players": "Top Players",
        "upcoming_competitions": "Upcoming Competitions",
        "view_all_competitions": "View all competitions",
        "no_upcoming": "No Upcoming Competitions",
        "no_upcoming_detail": "Check back later or wait for the scraper to fetch new events from FIS.",
        # Table headers (shared)
        "th_rank": "Rank",
        "th_player": "Player",
        "th_points": "Points",
        "th_athlete": "Athlete",
        "th_nation": "Nation",
        "th_competition": "Competition",
        "th_date": "Date",
        "th_position": "Position",
        # Error page
        "title_error": "Error",
        "back_to_home": "Back to Home",
        # Auth
        "title_login": "Login",
        "title_register": "Register",
        "label_username": "Username",
        "label_password": "Password",
        "label_password_confirm": "Confirm Password",
        "btn_login": "Login",
        "btn_register": "Register",
        "no_account": "Don't have an account?",
        "have_account": "Already have an account?",
        # Auth errors
        "err_username_short": "Username must be at least 3 characters.",
        "err_password_short": "Password must be at least 6 characters.",
        "err_password_mismatch": "Passwords do not match.",
        "err_username_taken": "Username already taken.",
        "err_invalid_credentials": "Invalid username or password.",
        # Competitions
        "title_competitions": "Competitions",
        "tab_upcoming": "Upcoming",
        "tab_completed": "Completed",
        "tab_all": "All",
        "no_competitions": "No competitions found.",
        "err_competition_not_found": "Competition not found.",
        # Competition detail
        "place_your_bet": "Place Your Bet",
        "place_1st": "1st Place",
        "place_2nd": "2nd Place",
        "place_3rd": "3rd Place",
        "placeholder_athlete": "Athlete name",
        "btn_place_bet": "Place Bet",
        "btn_update_bet": "Update Bet",
        "login_to_bet": "to place your bet!",
        "your_current_bet": "Your Current Bet",
        "betting_closed": "Betting closed — the competition has started.",
        "results": "Results",
        # My bets
        "title_my_bets": "My Bets",
        "pending": "Pending",
        "no_bets_yet": "You haven't placed any bets yet.",
        "browse_competitions": "Browse competitions",
        "to_get_started": "to get started!",
        # Ranking
        "title_ranking": "Ranking",
        "title_leaderboard": "Leaderboard",
        "no_players_yet": "No players yet.",
        "and_start_betting": "and start betting!",
    },
}


def translate(key: str, lang: str) -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]).get(key, key)


def format_date_localized(dt: date, lang: str) -> str:
    months = POLISH_MONTHS if lang == "pl" else ENGLISH_MONTHS
    return f"{dt.day:02d} {months[dt.month]} {dt.year}"
