"""
Bundeswehr Roleplay – Discord-Bot (alles in EINER Datei)

START:   1) pip install -r requirements.txt
         2) Datei .env neben diese Datei legen mit:   DISCORD_TOKEN=dein_bot_token
         3) python bot.py

WO ÄNDERE ICH WAS?
  • Servername, Farbe, Status, Bilder, Rollennamen, Dienstgrade, Einheiten, Ticket-Arten
        -> Abschnitt "EINSTELLUNGEN" direkt unter diesem Text (CONFIG_YAML)
  • Rollen, die bei Ereignissen gepingt werden            -> Abschnitt "EINSTELLUNGEN" (PINGS)
  • Texte der Nachrichten, Embeds und Buttons
        -> Abschnitt "TEXTE" (direkt unter "EINSTELLUNGEN"), nach Bereichen sortiert.
           {user}, {kanal} usw. sind Platzhalter und müssen stehen bleiben.
  • Befehlsnamen und Beschreibungen
        -> bei den Modulen weiter unten:  @app_commands.command(name="...", description="...")
  • Wer einen Befehl benutzen darf   -> bei dem Befehl:  @stufe("ausbilder")  (Stufen: siehe "berechtigungen" in den EINSTELLUNGEN)

Nach jeder Änderung den Bot neu starten.
"""
from __future__ import annotations

import aiosqlite
import ast
import datetime as dt
import discord
import io
import json
import logging
import os
import re
import sys
import time
import yaml
from dataclasses import dataclass, field
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString
from typing import Any
from typing import Iterable
from typing import Iterator
from zoneinfo import ZoneInfo

log = logging.getLogger("bwrp")


class _Modul:
    """Erlaubt u.embed(...), tx.setze_daten(...), ac.xyz(...) wie vorher, obwohl alles in einer Datei steht."""

    def __getattr__(self, name):
        try:
            return globals()[name]
        except KeyError:
            raise AttributeError(name) from None


u = tx = ac = _Modul()


# ==========================================================================
#  EINSTELLUNGEN  – hier änderst du Name, Farben, Bilder, Rollen, Einheiten, Dienstgrade ...
# ==========================================================================
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"          # hier liegt die Datenbank (bot.db)
DATA.mkdir(exist_ok=True)

# Server-ID, Name, Farbe, Status, Bilder, Berechtigungen, Einheiten, Dienstgrade, Tickets ... (YAML-Format, Einrückung beachten!)
CONFIG_YAML = r"""
# =====================================================================
#  BwRP Bot – Konfiguration
#  Rollen werden über ihren EXAKTEN Namen gefunden (inkl. "•" und Leerzeichen).
#  Nach Änderungen: Bot neu starten oder /setup neuladen
#  Mit /setup pruefen siehst du, welche Rollen nicht gefunden werden.
# =====================================================================

bot:
  name: "Bundeswehrkaserne"           # Footer unter jedem Embed
  guild_id: 1561812448460152963      # Server-ID (Befehle werden sofort auf diesem Server angezeigt)
  farbe: "#4E5B31"                   # Bundeswehr-Oliv
  status: "Bundeswehr Roleplay"       # wird angezeigt als: Schaut Bundeswehr Roleplay

# ---------------------------------------------------------------------
#  Berechtigungsstufen
#  rollen:  Rollen, die diese Stufe haben
#  plus:    Stufen, die AUTOMATISCH auch diese Stufe haben (Vererbung)
#  einheit_ab_position: jeder, der in IRGENDEINER Einheit mind. diese Position hat
#  Discord-Administratoren dürfen immer alles.
# ---------------------------------------------------------------------
berechtigungen:
  admin:
    rollen:
      - "[Admin Perms]"
      - "BwRP • Projektvorsitzender"
      - "BwRP • Projektdirektorium"
      - "BwRP • Stellv. Projektdirektorium"
      - "BwRP • Projektverwaltung"
      - "BwRP • High Team"
  management:
    rollen:
      - "BwRP • Teamkoordination"
      - "BwRP • Technische Leitung"
      - "BwRP • Manager"
      - "BwRP • Discord Manager"
      - "BwRP • Teamverwaltung"
    plus: [admin]
  moderator:
    rollen:
      - "BwRP • Head of Administrator"
      - "BwRP • Administrator"
      - "BwRP • Test Administrator"
      - "BwRP • Head of Game Moderator"
      - "BwRP • Game Moderator"
      - "BwRP • Head of Discord Moderator"
      - "BwRP • Discord Moderator"
    plus: [management]
  support:
    rollen:
      - "BwRP • Test Game Moderator"
      - "BwRP • Test Discord Moderator"
      - "BwRP • Head of Supporter"
      - "BwRP • Supporter"
      - "BwRP • Test Supporter"
      - "BwRP • Staff Team"
    plus: [moderator]
  projektmanagement:
    rollen:
      - "BwRP • Projektvorsitzender"
      - "BwRP • Projektdirektorium"
      - "BwRP • Stellv. Projektdirektorium"
      - "BwRP • Projektverwaltung"
  entbannung:
    rollen: ["BwRP • Entbannungsmanagement"]
    plus: [management]
  partner:
    rollen: ["BwRP • Partnerschaftsverwaltung"]
    plus: [management]
  developer:
    rollen:
      - "BwRP • Vollzeit Developer"
      - "BwRP • Head of Developer"
      - "BwRP • Developer"
      - "BwRP • Test Developer"
    plus: [admin]
  event:
    rollen: ["BwRP • Event Team"]
    plus: [kommando, management]
  kommando:
    rollen:
      - "BwRP • Bundesregierung"
      - "BwRP • Kasernenkommandant"
      - "BwRP • Divisionsleitung"
    plus: [admin]
  karriere:
    rollen:
      - "Abteilungsleitung • Karriere Center"
      - "Kompanieführung • Karriere Center"
      - "Karriereberater • Karriere Center"
    plus: [kommando]
  ausbilder:
    rollen:
      - "Abteilungsleiter • Ausbilder"
      - "Kompanieführung • Ausbilder"
      - "Ausbilder"
    plus: [kommando]
  personal:
    # Jeder ab "Personalabteilung" in irgendeiner Einheit + Kommando/Admin
    einheit_ab_position: 5
    plus: [kommando]

# ---------------------------------------------------------------------
#  Personalverwaltung
# ---------------------------------------------------------------------
personal:
  verwalten_ab_position: 5        # ab Position 5 (Personalabteilung) darf man seine Einheit verwalten
  basis_position: 1               # ab Position 1 bekommt man zusätzlich die Einheits-Grundrolle
  global_stufen: [admin, kommando]   # dürfen ALLE Einheiten komplett verwalten
  zusatzrollen: ["Soldaten*in"]   # bekommt jeder, der in eine Einheit eingestellt wird
  nickname:
    aktiv: false                  # true = Bot setzt Nicknames automatisch
    format: "[{einheit_kurz}] {dienstgrad_kurz} {name}"

# Positionen jeder Einheit – von UNTEN (0) nach OBEN. {einheit} wird ersetzt.
positionen_vorlage:
  - { titel: "Anwärter",          rolle: "[Free] {einheit}" }               # 0
  - { titel: "Mitglied",          rolle: "{einheit}" }                      # 1
  - { titel: "Führungsebene",     rolle: "Führungsebene • {einheit}" }      # 2
  - { titel: "Gruppenführer",     rolle: "Gruppenführer • {einheit}" }      # 3
  - { titel: "Zugführer",         rolle: "Zugführer • {einheit}" }          # 4
  - { titel: "Personalabteilung", rolle: "Personalabteilung • {einheit}" }  # 5
  - { titel: "Kompanieführung",   rolle: "Kompanieführung • {einheit}" }    # 6
  - { titel: "Leitung",           rolle: "Leitung • {einheit}" }            # 7

einheiten:
  - { name: "Kommando Spezialkräfte", kurz: "KSK",  emoji: "🗡️" }
  - { name: "Feldjäger",              kurz: "FJg",  emoji: "🚓" }
  - { name: "Wachbataillon",          kurz: "WachBtl", emoji: "💂" }
  - { name: "Marine",                 kurz: "Mar",  emoji: "⚓" }
  - { name: "Sanitätsdienst",         kurz: "San",  emoji: "🚑" }
  - { name: "ABC-Abwehrtruppe",       kurz: "ABC",  emoji: "☢️" }
  - { name: "Logistiktrupp",          kurz: "Log",  emoji: "🚚" }
  - { name: "United Nations",         kurz: "UN",   emoji: "🇺🇳" }
  - { name: "Kommando Luftwaffe",     kurz: "Lw",   emoji: "✈️" }
  - name: "Raider"
    kurz: "Raid"
    emoji: "🏴"
    positionen:                       # eigene Positionen statt Vorlage
      - { titel: "Anwärter", rolle: "[Free] Raider" }
      - { titel: "Mitglied", rolle: "Raider" }

# ---------------------------------------------------------------------
#  Dienstgrade (von unten nach oben)
# ---------------------------------------------------------------------
dienstgrade:
  - { name: "Schütze",            kurz: "S",       gruppe: "Mannschaften" }
  - { name: "Gefreiter",          kurz: "Gefr",    gruppe: "Mannschaften" }
  - { name: "Obergefreiter",      kurz: "OGefr",   gruppe: "Mannschaften" }
  - { name: "Hauptgefreiter",     kurz: "HptGefr", gruppe: "Mannschaften" }
  - { name: "Stabsgefreiter",     kurz: "StGefr",  gruppe: "Mannschaften" }
  - { name: "Oberstabsgefreiter", kurz: "OStGefr", gruppe: "Mannschaften" }
  - { name: "Unteroffizier",      kurz: "U",       gruppe: "Unteroffiziere ohne Portepee" }
  - { name: "Stabsunteroffizier", kurz: "StUffz",  gruppe: "Unteroffiziere ohne Portepee" }
  - { name: "Feldwebel",          kurz: "Fw",      gruppe: "Unteroffiziere mit Portepee" }
  - { name: "Oberfeldwebel",      kurz: "OFw",     gruppe: "Unteroffiziere mit Portepee" }
  - { name: "Hauptfeldwebel",     kurz: "HptFw",   gruppe: "Unteroffiziere mit Portepee" }
  - { name: "Stabsfeldwebel",     kurz: "StFw",    gruppe: "Unteroffiziere mit Portepee" }
  - { name: "Oberstabsfeldwebel", kurz: "OStFw",   gruppe: "Unteroffiziere mit Portepee" }
  - { name: "Leutnant",           kurz: "Lt",      gruppe: "Offiziere" }
  - { name: "Oberleutnant",       kurz: "OLt",     gruppe: "Offiziere" }
  - { name: "Hauptmann",          kurz: "Hptm",    gruppe: "Offiziere" }
  - { name: "Stabshauptmann",     kurz: "StHptm",  gruppe: "Offiziere" }
  - { name: "Major",              kurz: "Maj",     gruppe: "Stabsoffiziere" }
  - { name: "Oberstleutnant",     kurz: "OTL",     gruppe: "Stabsoffiziere" }
  - { name: "Oberst",             kurz: "O",       gruppe: "Stabsoffiziere" }
  - { name: "Brigadegeneral",     kurz: "BG",      gruppe: "Generale" }
  - { name: "Generalmajor",       kurz: "GM",      gruppe: "Generale" }
  - { name: "Generalleutnant",    kurz: "GL",      gruppe: "Generale" }
  - { name: "General",            kurz: "Gen",     gruppe: "Generale" }

# ---------------------------------------------------------------------
#  Bewerbungen (Karriere Center)
# ---------------------------------------------------------------------
#  Alle Texte (Panel, Antworten, DMs) stehen im Code, Suche nach T-karriere
bewerbung:
  panel_bild: ""
  einheit_waehlen: true
  einheiten: []                 # leer = alle Einheiten; sonst z. B. ["Feldjäger", "Marine"]
  per_dm: true                  # true = nach der Einheiten-Wahl kommt eine DM mit "Fortfahren" / "Abbrechen"
  #  Eigener Kanal pro Einheit: /setup bewerbungskanal  (oder alle auf einmal: /setup bewerbungskanaele_erstellen)
  team_pingen: false            # true = Karriere-Team bei neuer Bewerbung pingen (weitere Pings: PINGS oben)
  sperre_nach_ablehnung_tage: 3
  einheit_frage: "Für welche Division möchtest du dich als Divisionsleitung bewerben?"   # Frage 1 (Auswahlmenü)
  #  Weitere Fragen: beliebig viele. Pro Formular erscheinen 5 (Discord-Limit), danach kommt ein "Weiter"-Knopf.
  #  frage = voller Text (steht in der Bewerbung und im Eingabefeld als Platzhalter)
  #  kurz  = Beschriftung über dem Eingabefeld (max. 45 Zeichen)
  #  lang: true = großes Textfeld · max = maximale Zeichen · pflicht: false = darf leer bleiben
  fragen:
    - { frage: "Wie heißt du und wie alt bist du?", kurz: "Name und Alter", max: 100 }
    - { frage: "Wie lautet dein Roblox-Name?", kurz: "Roblox-Name", max: 50 }
    - { frage: "Warum möchtest du Divisionsleitung werden?", kurz: "Warum Divisionsleitung?", lang: true }
    - { frage: "Welche Erfahrungen hast du bereits im Führungsbereich gesammelt?", kurz: "Führungserfahrung", lang: true }
    - { frage: "Was macht deiner Meinung nach eine gute Divisionsleitung aus?", kurz: "Was macht eine gute Divisionsleitung aus?", lang: true }
    - { frage: "Wie würdest du deine Division organisieren und strukturieren?", kurz: "Organisation und Struktur", lang: true }
    - { frage: "Wie würdest du mit inaktiven Mitgliedern umgehen?", kurz: "Umgang mit inaktiven Mitgliedern", lang: true }
    - { frage: "Wie würdest du einen Streit innerhalb deiner Division lösen?", kurz: "Streit in der Division lösen", lang: true }
    - { frage: "Wie würdest du neue Mitglieder für deine Division gewinnen?", kurz: "Neue Mitglieder gewinnen", lang: true }
    - { frage: "Wie würdest du deine Ausbilder und Stellvertreter koordinieren?", kurz: "Ausbilder und Stellvertreter koordinieren", lang: true }
    - { frage: "Was würdest du tun, wenn ein hochrangiges Mitglied seine Rechte missbraucht?", kurz: "Rechtemissbrauch durch hochrangiges Mitglied", lang: true }
    - { frage: "Wie würdest du dafür sorgen, dass die Dienstvorschriften eingehalten werden?", kurz: "Einhaltung der Dienstvorschriften", lang: true }
    - { frage: "Wie viel Zeit kannst du täglich für deine Division investieren?", kurz: "Tägliche Zeit für die Division", max: 100 }
    - { frage: "Warum sollten wir gerade dich als Divisionsleitung annehmen?", kurz: "Warum sollten wir dich annehmen?", lang: true }
  bei_annahme:
    rollen: []                   # z. B. ["Divisionsleitung"] – Rollen, die bei Annahme automatisch vergeben werden
    in_einheit_eintragen: false  # true = Person wird zusätzlich als Anwärter in die gewählte Division eingetragen
    position: 0

ausbildung:
  lehrgaenge:
    - "Grundausbildung"
    - "Waffenausbildung"
    - "Sanitätslehrgang"
    - "Fahrschule"
    - "Funklehrgang"
    - "Feldjäger-Lehrgang"
    - "Fallschirmspringer-Lehrgang"
    - "Einzelkämpfer-Lehrgang"
    - "Gruppenführer-Lehrgang"
    - "Zugführer-Lehrgang"
  rollen_nach_lehrgang:          # optional: Rolle automatisch vergeben
    # "Grundausbildung": "Soldaten*in"

# ---------------------------------------------------------------------
dienst:
  max_stunden: 12               # Dienst wird danach automatisch beendet
  nur_soldaten: true            # nur eingetragene Soldaten können in den Dienst
  im_dienst_rolle: ""           # optional: Rolle während des Dienstes, z. B. "Im Dienst"

events:
  erinnerung_minuten: 15

moderation:
  warn_automatik:               # automatische Strafe bei X Verwarnungen
    - { ab: 3, aktion: timeout, dauer: "1h" }
    - { ab: 5, aktion: timeout, dauer: "1d" }
    - { ab: 7, aktion: kick }

#  Panel-Texte der Tickets: im Code: T-Texte tickets
tickets:
  max_pro_user: 2
  team_pingen: true
  transkript_an_user: true
  #  Jede Art kann eine eigene Discord-Kategorie haben:
  #    kategorie: "Name der Kategorie" oder ID  – fehlt sie, wird sie automatisch erstellt
  #    oder in Discord: /setup kategorie kategorie:<Kategorie> art:<Art>
  #  Ohne Angabe landet das Ticket in der allgemeinen Kategorie (/setup kategorie ohne art)
  arten:
    - { name: "Support",        kuerzel: "support",  emoji: "🛠️", beschreibung: "Allgemeine Fragen & Hilfe", team: [support], kategorie: "🛠️ Support-Tickets" }
    - { name: "Beschwerde",     kuerzel: "beschwerde", emoji: "⚖️", beschreibung: "Beschwerde über ein Mitglied", team: [moderator], kategorie: "⚖️ Beschwerden" }
    - { name: "Bewerbung Team", kuerzel: "team",     emoji: "📋", beschreibung: "Bewerbung für das Serverteam", team: [management], kategorie: "📋 Team-Bewerbungen" }
    - { name: "Entbannung",     kuerzel: "entbann",  emoji: "🔓", beschreibung: "Entbannungsantrag (Game)", team: [entbannung], kategorie: "🔓 Entbannungen" }
    - { name: "Partnerschaft",  kuerzel: "partner",  emoji: "🤝", beschreibung: "Partnerschaftsanfrage", team: [partner], kategorie: "🤝 Partnerschaften" }
    - { name: "Projektmanagement", kuerzel: "projekt", emoji: "🏛️", beschreibung: "Anliegen an die Projektleitung", team: [projektmanagement], kategorie: "🏛️ Projektmanagement" }
    - { name: "Technik / Bug",  kuerzel: "bug",      emoji: "🐞", beschreibung: "Fehler melden", team: [developer], kategorie: "🐞 Bug-Meldungen" }

#  Willkommens-/Abschiedstexte: im Code: T-Texte willkommen
willkommen:
  autorollen: []                # z. B. ["Besucher"]
  bild: ""
  dm: false

"""

PINGS = {
    # Welche Rollen sollen bei bestimmten Ereignissen gepingt werden? Rollenname, Rollen-ID, "everyone" oder "here".
    # Beispiel:  "event_erstellt": ["Rekruten", "Mannschaften"],
    "befoerderung": [],          # Beförderung / Uprank / neue Position (Kanal: befoerderungen)
    "bewerbung_eingang": [],     # neue Bewerbung im Bewerbungs-Kanal
    "ticket_erstellt": [],       # neues Ticket (zusätzlich zum zuständigen Team)
    "event_erstellt": [],        # /event erstellen (zusätzlich zur gewählten Rolle)
    "appell": [],                # /appell starten (zusätzlich zur gewählten Rolle)
    "willkommen": [],            # Willkommensnachricht (der neue User wird immer gepingt)
    "abmeldung": [],             # neue Abmeldung im Abmelde-Kanal
    "ankuendigung": [],          # /ankuendigung (zusätzlich zur gewählten Rolle)
    "umfrage": [],               # /umfrage (zusätzlich zur gewählten Rolle)
    "ausbildung_ankuendigung": [],  # /ausbildungs-ankuendigung (zusätzlich zur gewählten Rolle)
}

# ==========================================================================
#  TEXTE – ALLE Nachrichten, Embed-Titel, Embed-Texte und Button-Beschriftungen
#  Ändere hier einfach den Text rechts vom Doppelpunkt. Nach dem Speichern den Bot neu starten.
#  • {user}, {kanal}, {einheit} ... sind Platzhalter – die müssen genau so stehen bleiben.
#  • \n bedeutet neue Zeile, **text** macht Text fett, # am Anfang macht eine Überschrift.
#  • Emojis kannst du einfach austauschen.
#  • Bilder, Farben, Servername und Fragen der Bewerbung stehen oben in CONFIG_YAML.
#  • Gepingte Rollen stehen oben bei PINGS.
#  Übersicht der Bereiche:  Bewerbung · Willkommen · Ausbildungs-Ankündigung · Personal (Uprank/Downrank)
#  · Ausbildung · Tickets · Events · Appell · Dienst · Abmeldungen · Moderation · Einheiten · Logs · Setup · Allgemein
# ==========================================================================
TEXTE = {

    # ----------------------------------------------------------------------
    #  BEWERBUNG (Divisionsleitung): Panel, Formular, DMs, Bewerbungs-Embed
    # ----------------------------------------------------------------------
    "karriere": {
        "schon_offen": "Du hast schon eine offene Bewerbung (#{nummer}).",
        "gesperrt": "Du kannst dich erst wieder {zeit} bewerben.",
        "einheit_frage": "Für welche Division bewirbst du dich?",
        "knopf_weiter": "Weiter zu Teil {teil}/{gesamt}",
        "nicht_deins": "Das ist nicht deine Bewerbung.",
        "modal_titel": "{einheit} – Teil {teil}/{gesamt}",
        "teil_fertig_titel": "✅ Teil {teil}/{gesamt} gespeichert",
        "teil_fertig_text": "Als Nächstes kommen diese Fragen:\n{fragen}\n\nKlicke auf **Weiter**, um fortzufahren. Du hast 30 Minuten Zeit.",
        "server_weg": "Der Server ist nicht erreichbar.",
        "kein_kanal": "Der Bewerbungs-Kanal ist nicht eingerichtet. Melde dich beim Team.",
        "eingereicht": "Deine Bewerbung **#{nummer}** für **{einheit}** wurde eingereicht. Du bekommst eine DM, sobald sie bearbeitet wurde.",
        "eingereicht_titel": "Bewerbung eingereicht",
        "dm_knopf_fortfahren": "Bewerbung fortfahren",
        "dm_knopf_abbrechen": "Abbrechen",
        "dm_knopf_abbrechen_emoji": "✖️",
        "dm_knopf_fortfahren_emoji": "📝",
        "dm_abgebrochen_titel": "✖️ Bewerbung abgebrochen",
        "dm_abgebrochen": "Kein Problem. Du kannst dich jederzeit über das Karriere Center neu bewerben.",
        "dm_start_text": "Hallo {user}, du möchtest dich als **Divisionsleitung** der Division **{einheit}** auf **{server}** bewerben.\n\nKlicke auf **Bewerbung fortfahren**, um die Fragen zu beantworten (mehrere kurze Formulare), oder auf **Abbrechen**.",
        "dm_start_titel": "📝 Bewerbung – {einheit}",
        "dm_zu": "Ich kann dir keine DM schicken. Erlaube in den Server-Einstellungen unter **Privatsphäre** Direktnachrichten von Servermitgliedern und versuche es erneut.",
        "dm_gesendet": "Ich habe dir eine DM geschickt: {link}",
        "dm_gesendet_titel": "Schau in deine DMs",
        "status_angenommen": "angenommen",
        "status_offen": "Offen",
        "status_abgelehnt": "abgelehnt",
        "embed_titel": "📨 Bewerbung #{nummer} – {einheit}",
        "embed_text": "Von {user} (`{name}`)\nAccount erstellt: {erstellt}",
        "embed_fortsetzung": "📨 Bewerbung #{nummer} – Fortsetzung ({seite}/{gesamt})",
        "feld_status": "Status",
        "ablehnen_titel": "Bewerbung ablehnen",
        "ablehnen_grund": "Grund",
        "knopf_ablehnen": "Ablehnen",
        "knopf_annehmen": "Annehmen",
        "knopf_ablehnen_emoji": "❌",
        "knopf_annehmen_emoji": "✅",
        "nur_team": "Nur das Karriere Center darf das.",
        "einheit_waehlen": "Division auswählen …",
        "knopf_bewerben": "Jetzt bewerben",
        "knopf_bewerben_emoji": "📝",
        "schon_bearbeitet": "Die Bewerbung wurde schon bearbeitet.",
        "log_einstellung": "Einstellung (Bewerbung)",
        "nicht_mehr_da": "⚠️ Die Person ist nicht mehr auf dem Server.",
        "feld_bearbeiter": "Bearbeitet von",
        "dm_angenommen": "Deine Bewerbung als Divisionsleitung für **{einheit}** wurde **angenommen**.\n\nHerzlichen Glückwunsch! Das Team meldet sich bei dir.",
        "dm_angenommen_titel": "📨 Bewerbung angenommen",
        "dm_abgelehnt": "Deine Bewerbung für **{einheit}** wurde **abgelehnt**.\nGrund: {grund}\n\nDu kannst dich in ein paar Tagen erneut bewerben.",
        "dm_abgelehnt_titel": "📨 Bewerbung abgelehnt",
        "bearbeitet_ok": "Bewerbung #{nummer} {status}.",
        "panel_text": "Du möchtest eine **Division** der **Bundeswehrkaserne** leiten?\nKlicke auf **Jetzt bewerben**, wähle deine Division und beantworte die Fragen.\nDas Karriere Center meldet sich per DM bei dir.",
        "panel_titel": "📝 Bundeswehr Karriere Center",
        "liste_titel": "📨 Bewerbungen ({status})",
    },

    # ----------------------------------------------------------------------
    #  WILLKOMMEN / ABSCHIED (Texte, wenn jemand beitritt oder geht)
    # ----------------------------------------------------------------------
    "willkommen": {
        "titel": "🇩🇪 Willkommen in der Bundeswehrkaserne !",
        "text": "Moin {user}! Schön, dass du da bist.\nBei uns stehen **Disziplin, Respekt und Kameradschaft** an erster Stelle.\nLies dir die Regeln durch und bewirb dich im Karriere Center.\nDu bist Mitglied Nr. **{mitglieder}**.",
        "setup_ok": "Willkommensnachrichten erscheinen jetzt in {kanal}.\nMit `/willkommen test` siehst du eine Vorschau.",
        "vorschau": "**Vorschau:**",
        "reset_ok": "Standard-Willkommensnachricht wiederhergestellt.",
        "dm_titel": "Willkommen auf {server}",
        "dm_text": "Willkommen auf {server}! Bewirb dich doch gerne im Karriere Center, um richtig loszulegen.",
        "abschied_titel": "👋 Auf Wiedersehen",
        "abschied": "**{user_name}** hat die Kaserne verlassen.",
    },

    # ----------------------------------------------------------------------
    #  AUSBILDUNGS-ANKÜNDIGUNG (/ausbildungs-ankuendigung)
    # ----------------------------------------------------------------------
    "ausbildung_ankuendigung": {
        "kopf": "# 🎓 Ausbildungszentrum der Bundeswehr",
        "text": "Liebe Rekruten! {ausbilder} lädt zur nächsten Ausbildung ein.\nAlle wichtigen Details findet ihr unten. Seid pünktlich und kommt vorbereitet!",
        "titel": "Ausbildungs-Infos",
        "feld_rang": "⛑️ Ausbildungsrang",
        "feld_pad": "#️⃣ Ausbildungs Ort",
        "feld_uhrzeit": "🕐 Uhrzeit",
        "feld_ausbilder": "📋 Ausbilder",
        "feld_server": "💻 Server",
        "ok": "Ankündigung in {kanal} gepostet.",
    },

    # ----------------------------------------------------------------------
    #  PERSONAL: Einstellen, Uprank, Downrank, Beförderung, Akte
    # ----------------------------------------------------------------------
    "personal": {
        "einheit_unbekannt": "Unbekannte Einheit.",
        "log_titel": "📁 {aktion}",
        "log_durch": "Durch",
        "darf_einheit_nicht": "Du darfst die Einheit **{einheit}** nicht verwalten.",
        "nur_unterhalb": "Du kannst nur Positionen **unterhalb** deiner eigenen vergeben.",
        "nicht_selbst": "Du kannst dich nicht selbst bearbeiten.",
        "zu_hoch": "Diese Person steht gleich hoch oder höher als du.",
        "rollen_fehlen": "⚠️ Diese Rollen gibt es nicht auf dem Server: {rollen}",
        "position_ungueltig": "Ungültige Position.",
        "schon_in_einheit": "{user} ist schon bei **{einheit}**. Nutze `/personal versetzen`.",
        "aktion_einstellung": "Einstellung",
        "einstellung_log": "{emoji} **{einheit}** als **{position}**",
        "einstellung_dm_titel": "{emoji} Willkommen in der Einheit {einheit}",
        "einstellung_dm": "Du wurdest auf **{server}** als **{position}** eingestellt.",
        "einstellung_ok": "{user} ist jetzt **{position}** bei **{einheit}**.",
        "nicht_eingetragen": "Diese Person ist in keiner Einheit eingetragen.",
        "aktion_position": "Positionswechsel",
        "grund": "Grund: {grund}",
        "position_bekanntgabe_titel": "🎖️ Neue Position",
        "position_bekanntgabe": "{user} wurde von {von} zum **{position}** bei {emoji} **{einheit}** aufgestuft. Herzlichen Glückwunsch!",
        "uprank_rolle_ungueltig": "Diese Rolle kann nicht vergeben werden.",
        "uprank_bot_zu_niedrig": "Die Bot-Rolle muss über {rolle} stehen.",
        "uprank_zu_hoch": "Du kannst nur Rollen vergeben, die unter deiner höchsten Rolle stehen.",
        "uprank_schon": "{user} hat {rolle} bereits.",
        "uprank_fehler": "Konnte die Rolle nicht vergeben.",
        "aktion_uprank": "Uprank",
        "uprank_titel": "🎖️ Uprank",
        "uprank_text": "{user} wurde von {von} zu {rolle} aufgestuft. Herzlichen Glückwunsch!",
        "uprank_dm_titel": "🎖️ Uprank",
        "uprank_dm": "Du wurdest von {von} zu **{rolle}** aufgestuft.",
        "uprank_ok": "{user} wurde zu {rolle} aufgestuft.",
        "downrank_rolle_ungueltig": "Diese Rolle kann nicht entfernt werden.",
        "downrank_zu_hoch": "Du kannst nur Rollen entfernen, die unter deiner höchsten Rolle stehen.",
        "downrank_hat_nicht": "{user} hat {rolle} gar nicht.",
        "downrank_fehler": "Konnte die Rolle nicht entfernen.",
        "aktion_downrank": "Downrank",
        "downrank_titel": "📉 Downrank",
        "downrank_text": "{user} wurde von {von} aus {rolle} abgestuft.",
        "downrank_dm_titel": "📉 Downrank",
        "downrank_dm": "Du wurdest von {von} aus **{rolle}** abgestuft.",
        "downrank_ok": "{user} wurde aus {rolle} abgestuft.",
        "keine_dienstgrade": "In der config.yaml sind keine Dienstgrade definiert.",
        "kein_dienstgrad": "Es gibt keinen höheren/niedrigeren Dienstgrad.",
        "nur_unter_eigenem": "Du kannst nur bis unter deinen eigenen Dienstgrad befördern.",
        "befoerderung_titel": "🎖️ Beförderung",
        "befoerderung_text": "{user} wurde von {von} zum **{dienstgrad}** befördert. Herzlichen Glückwunsch!",
        "dienstgrad_dm_titel": "🎖️ {aktion}",
        "dienstgrad_dm": "Dein Dienstgrad: {alt} → **{neu}**",
        "aktion_befoerderung": "Beförderung",
        "aktion_degradierung": "Degradierung",
        "aktion_dienstgrad": "Dienstgrad geändert",
        "einheit_position_unbekannt": "Unbekannte Einheit oder Position.",
        "alte_einheit": "Alte Einheit: {fehler}",
        "neue_einheit": "Neue Einheit: {fehler}",
        "aktion_versetzung": "Versetzung",
        "versetzt_ok": "{user} wurde zu **{einheit}** versetzt.",
        "aktion_entlassung": "Entlassung",
        "entlassung_log": "aus **{einheit}**\nGrund: {grund}",
        "entlassung_dm": "Du wurdest aus **{einheit}** entlassen.\nGrund: {grund}",
        "entlassung_dm_titel": "📄 Entlassung",
        "entlassen_ok": "{user} wurde aus **{einheit}** entlassen.",
        "rpname_ok": "RP-Name von {user}: **{name}**",
        "notiz_ok": "Notiz zu {user} gespeichert.",
        "kein_verlauf": "Kein Verlauf.",
        "verlauf_titel": "📜 Verlauf – {name}",
        "nur_eigene_akte": "Du darfst nur deine eigene Akte ansehen.",
        "akte_titel": "🗂️ Personalakte – {name}",
        "feld_einheit": "Einheit",
        "feld_position": "Position",
        "feld_dienstgrad": "Dienstgrad",
        "feld_rpname": "RP-Name",
        "feld_eintritt": "Eintritt",
        "akte_keine_einheit": "Aktuell in keiner Einheit eingetragen.",
        "feld_dienstzeit": "Dienstzeit gesamt",
        "feld_lehrgaenge": "Lehrgänge ({anzahl})",
        "feld_warns": "Verwarnungen",
        "feld_notizen": "🔒 Interne Notizen",
    },

    # ----------------------------------------------------------------------
    #  AUSBILDUNG / LEHRGÄNGE
    # ----------------------------------------------------------------------
    "ausbildung": {
        "schon_eingetragen": "Ist schon eingetragen.",
        "rolle_vergeben": "Rolle {rolle} vergeben.",
        "rolle_fehler": "⚠️ Konnte Rolle nicht vergeben.",
        "log_titel": "Lehrgang bestanden",
        "log_text": "🎓 **{lehrgang}**",
        "dm_text": "Glückwunsch! Du hast **{lehrgang}** bestanden.",
        "dm_titel": "🎓 Lehrgang bestanden",
        "bestanden_ok": "{user} hat **{lehrgang}** bestanden.",
        "entfernt": "**{lehrgang}** bei {user} entfernt.",
        "liste_titel": "🎓 Lehrgänge – {name}",
        "event_titel": "🎓 {lehrgang}",
        "event_text": "Ausbilder: {user}",
    },

    # ----------------------------------------------------------------------
    #  TICKETSYSTEM
    # ----------------------------------------------------------------------
    "tickets": {
        "modal_titel": "Ticket – {art}",
        "modal_frage": "Worum geht es?",
        "auswahl": "Wähle eine Ticket-Art …",
        "schliessen_titel": "Ticket schließen",
        "schliessen_grund": "Grund (optional)",
        "knopf_uebernehmen": "Übernehmen",
        "knopf_uebernehmen_emoji": "🙋",
        "knopf_schliessen": "Schließen",
        "knopf_schliessen_emoji": "🔒",
        "schon_offen": "Du hast schon offene Tickets: {tickets}",
        "ticket_titel": "{emoji} Ticket #{nummer} – {art}",
        "ticket_text": "Danke für dein Ticket! Das Team meldet sich gleich bei dir.",
        "feld_ersteller": "Erstellt von",
        "feld_anliegen": "Anliegen",
        "erstellt_ok": "Dein Ticket: {kanal}",
        "nur_team": "Nur das Team kann Tickets übernehmen.",
        "kein_ticket": "Das ist kein Ticket.",
        "schon_uebernommen": "Schon übernommen von {user}.",
        "uebernommen_text": "{user} kümmert sich um dein Anliegen.",
        "uebernommen_titel": "🙋 Ticket übernommen",
        "wird_geschlossen": "🔒 Ticket wird geschlossen …",
        "geschlossen_titel": "🎫 Ticket #{nummer} geschlossen",
        "geschlossen_art": "Art: **{art}**",
        "feld_geschlossen_von": "Geschlossen von",
        "feld_bearbeiter": "Bearbeitet von",
        "feld_grund": "Grund",
        "panel_text": "Wähle unten aus, worum es geht. Ein Teammitglied kümmert sich schnellstmöglich darum.\n\n{arten}",
        "panel_titel": "🎫 Support & Tickets",
        "hinzugefuegt": "{user} wurde hinzugefügt.",
        "entfernt": "{user} wurde entfernt.",
        "umbenannt": "Umbenannt in **{name}**.",
    },

    # ----------------------------------------------------------------------
    #  EVENTS / EINSÄTZE
    # ----------------------------------------------------------------------
    "events": {
        "symbol_einsatz": "🚨",
        "symbol_event": "🎉",
        "symbol_ausbildung": "🎓",
        "symbol_uebung": "🎯",
        "symbol_besprechung": "📋",
        "symbol_parade": "🎖️",
        "knopf_zusagen": "Zusagen",
        "knopf_zusagen_emoji": "✅",
        "knopf_vielleicht": "Vielleicht",
        "knopf_vielleicht_emoji": "❔",
        "knopf_absagen": "Absagen",
        "knopf_absagen_emoji": "❌",
        "embed_titel": "{emoji} {art}: {titel}",
        "feld_zeit": "🕒 Zeitpunkt",
        "feld_ort": "📍 Ort",
        "feld_leitung": "👤 Leitung",
        "beendet_titel": "[ABGESAGT/BEENDET] {titel}",
        "erstellt_ok": "{art} **#{nummer}** erstellt: {link}",
        "nicht_aktiv": "Dieses Event ist nicht mehr aktiv.",
        "nicht_gefunden": "Event nicht gefunden.",
        "abgesagt_titel": "❌ {art} abgesagt: {titel}",
        "abgesagt_ok": "Event #{nummer} abgesagt.",
        "liste_titel": "📅 Kommende Events",
        "erinnerung_titel": "⏰ Erinnerung: {titel}",
        "erinnerung_text": "Beginnt {zeit}!",
    },

    # ----------------------------------------------------------------------
    #  APPELL
    # ----------------------------------------------------------------------
    "appell": {
        "knopf": "Anwesend melden",
        "knopf_emoji": "🫡",
        "beendet": "Dieser Appell ist beendet.",
        "gemeldet": "Anwesenheit gemeldet. 🫡",
        "standard_titel": "Morgenappell",
        "text": "Alle {wer} antreten!\nMeldet euch bis {uhrzeit} ({restzeit}) als anwesend.",
        "titel": "🫡 {titel}",
        "keiner": "Kein laufender Appell.",
        "beendet_ok": "Appell beendet.",
        "ergebnis": "📋 Ergebnis: {titel}",
        "anwesend": "✅ Anwesend ({anzahl})",
        "entschuldigt": "📅 Entschuldigt ({anzahl})",
        "unentschuldigt": "❌ Unentschuldigt ({anzahl})",
    },

    # ----------------------------------------------------------------------
    #  DIENST
    # ----------------------------------------------------------------------
    "dienst": {
        "woche": "Diese Woche",
        "monat": "Dieser Monat",
        "gesamt": "Gesamt",
        "nur_soldaten": "Nur eingetragene Soldaten können in den Dienst gehen.",
        "schon_im_dienst": "Du bist schon seit {zeit} im Dienst.",
        "log_start_titel": "🟢 Dienstbeginn",
        "log_start": "{user} ist in den Dienst gegangen.",
        "start_ok": "Du bist jetzt **im Dienst**. Viel Erfolg, Soldat!",
        "start_titel": "Dienstbeginn",
        "kein_dienst": "Kein laufender Dienst.",
        "log_ende_titel": "🔴 Dienstende",
        "log_ende": "{user} hat den Dienst beendet. Dauer: **{dauer}**",
        "log_beendet_durch": "Beendet durch {user}",
        "ende_ok": "Dienst von {user} beendet.\nDauer: **{dauer}** · Diese Woche: **{woche}**",
        "ende_titel": "Dienstende",
        "statistik_titel": "⏱️ Dienstzeit – {name}",
        "anzahl": "Dienste",
        "status": "Status",
        "status_im_dienst": "🟢 Im Dienst seit {zeit}",
        "status_ausser_dienst": "🔴 Außer Dienst",
        "aktiv_zeile": "🟢 {user} – seit {zeit}",
        "aktiv_titel": "🪖 Im Dienst ({anzahl})",
        "niemand": "Niemand im Dienst.",
        "platz1": "🥇",
        "platz2": "🥈",
        "platz3": "🥉",
        "keine_daten": "Keine Daten.",
        "rangliste_titel": "🏆 Dienst-Rangliste ({zeitraum})",
        "panel_text": "Melde dich hier zum Dienst an und ab.",
        "panel_titel": "🪖 Dienststelle",
        "reset_ok": "Dienstzeiten von {user} gelöscht.",
        "dauer_ungueltig": "Ungültige Dauer, z. B. `2h30m`.",
        "nachgetragen": "**{dauer}** für {user} nachgetragen.",
        "auto_ende": "Dein Dienst wurde automatisch beendet (Maximaldauer erreicht).",
        "auto_ende_titel": "Dienst",
    },

    # ----------------------------------------------------------------------
    #  ABMELDUNGEN
    # ----------------------------------------------------------------------
    "abmeldung": {
        "datum_format": "Datum bitte als `TT.MM.JJJJ`.",
        "bis_vor_von": "'bis' liegt vor 'von'.",
        "text": "{user} ist abgemeldet.",
        "titel": "📅 Abmeldung #{nummer}",
        "von": "Von",
        "bis": "Bis",
        "grund": "Grund",
        "ok": "Abmeldung eingetragen.",
        "zurueck_text": "{user} ist wieder da.",
        "zurueck_titel": "📅 Zurückgemeldet",
        "zurueck_ok": "Willkommen zurück.",
        "zeile": "{user} – {von} bis {bis} · {grund}",
        "liste_titel": "📅 Abmeldungen ({anzahl})",
        "niemand": "Niemand abgemeldet.",
        "geloescht": "Abmeldung #{nummer} gelöscht.",
    },

    # ----------------------------------------------------------------------
    #  MODERATION
    # ----------------------------------------------------------------------
    "mod": {
        "feld_moderator": "Moderator",
        "feld_grund": "Grund",
        "nicht_selbst": "Nicht an dir selbst.",
        "nicht_bot": "Netter Versuch.",
        "zu_hoch": "Diese Person steht gleich hoch oder über dir.",
        "bot_zu_niedrig": "Meine Bot-Rolle steht unter dieser Person.",
        "warn_dm": "Du wurdest auf **{server}** verwarnt.\nGrund: {grund}\nVerwarnungen gesamt: **{anzahl}**",
        "warn_dm_titel": "⚠️ Verwarnung",
        "warn_log": "⚠️ Verwarnung #{nummer}",
        "warn_gesamt": "Verwarnungen gesamt: **{anzahl}**",
        "warn_ok": "{user} verwarnt (**{anzahl}** gesamt).",
        "auto_grund": "Automatisch: {anzahl} Verwarnungen",
        "auto_timeout_log": "⏳ Auto-Timeout",
        "auto_timeout": "➡️ Automatischer Timeout ({dauer}).",
        "auto_kick_log": "👢 Auto-Kick",
        "auto_kick": "➡️ Automatisch gekickt.",
        "auto_ban_log": "🔨 Auto-Bann",
        "auto_ban": "➡️ Automatisch gebannt.",
        "auto_fehler": "⚠️ Automatik fehlgeschlagen (fehlende Rechte).",
        "warns_titel": "⚠️ Verwarnungen – {name} ({anzahl})",
        "keine_warns": "Keine.",
        "warn_entfernt": "Verwarnung #{nummer} entfernt.",
        "warns_geleert": "Alle Verwarnungen von {user} gelöscht.",
        "dauer_ungueltig": "Dauer z. B. `10m`, `1h`, max. 28 Tage.",
        "timeout_dm": "Du bist für **{dauer}** im Timeout.\nGrund: {grund}",
        "timeout_dm_titel": "⏳ Timeout",
        "timeout_log": "⏳ Timeout",
        "dauer": "Dauer: **{dauer}**",
        "timeout_ok": "{user} ist für **{dauer}** im Timeout.",
        "timeout_aufgehoben_log": "✅ Timeout aufgehoben",
        "timeout_aufgehoben": "Timeout von {user} aufgehoben.",
        "kick_dm": "Du wurdest von **{server}** gekickt.\nGrund: {grund}",
        "kick_dm_titel": "👢 Gekickt",
        "kick_log": "👢 Kick",
        "kick_ok": "{user} wurde gekickt.",
        "ban_dm": "Du wurdest von **{server}** gebannt.\nGrund: {grund}\n\nEinen Entbannungsantrag kannst du beim Entbannungsmanagement stellen.",
        "ban_dm_titel": "🔨 Gebannt",
        "ban_log": "🔨 Bann",
        "ban_ok": "{user} wurde gebannt.",
        "unban_fehler": "User nicht gefunden oder nicht gebannt.",
        "unban_log": "🔓 Entbannung",
        "unban_ok": "{user} wurde entbannt.",
        "clear_log": "🧹 Nachrichten gelöscht",
        "clear_log_text": "**{anzahl}** Nachrichten in {kanal}",
        "clear_ok": "**{anzahl}** Nachrichten gelöscht.",
        "slowmode_ok": "Slowmode: **{sekunden}s**",
        "gesperrt_text": "Dieser Kanal wurde gesperrt.",
        "gesperrt_titel": "🔒 Kanal gesperrt",
        "gesperrt_ok": "{kanal} gesperrt.",
        "entsperrt_titel": "🔓 Kanal entsperrt",
        "entsperrt_ok": "{kanal} entsperrt.",
        "nick_ok": "Nickname von {user} → **{name}**",
        "rolle_zu_hoch": "Diese Rolle steht über deiner höchsten Rolle.",
        "rolle_entfernt_log": "🏷️ Rolle entfernt",
        "rolle_gegeben_log": "🏷️ Rolle gegeben",
        "rolle_gegeben": "{rolle} an {user} gegeben.",
        "rolle_entfernt": "{rolle} von {user} entfernt.",
    },

    # ----------------------------------------------------------------------
    #  EINHEITEN-INFOS (/einheit ...)
    # ----------------------------------------------------------------------
    "einheit": {
        "zeile": "{emoji} **{name}** ({kurz}) – {anzahl} Soldaten",
        "gesamt": "**Gesamt:** {anzahl} aktive Soldaten",
        "titel": "🪖 Einheiten",
        "keine_mitglieder": "Keine Mitglieder.",
        "mitglieder_titel": "{emoji} {name} – {anzahl} Mitglieder",
        "dienstgrade_titel": "🎖️ Dienstgrade",
    },

    # ----------------------------------------------------------------------
    #  LOGS (Beitritt, gelöschte/bearbeitete Nachrichten)
    # ----------------------------------------------------------------------
    "logs": {
        "beitritt": "📥 Beitritt",
        "account_erstellt": "Account erstellt {zeit}",
        "verlassen": "📤 Verlassen",
        "geloescht": "🗑️ Nachricht gelöscht",
        "von_in": "Von {user} in {kanal}",
        "inhalt": "Inhalt",
        "anhaenge": "Anhänge",
        "bearbeitet": "✏️ Nachricht bearbeitet",
        "vorher": "Vorher",
        "nachher": "Nachher",
    },

    # ----------------------------------------------------------------------
    #  SETUP-BEFEHLE (/setup ...)
    # ----------------------------------------------------------------------
    "setup": {
        "kanal_gesetzt": "**{typ}** → {kanal}",
        "kanal_entfernt": "**{typ}** entfernt.",
        "art_unbekannt": "Diese Ticket-Art gibt es nicht.",
        "kategorie_art_ok": "**{art}**-Tickets landen in **{kategorie}**.",
        "kategorie_ok": "Tickets landen in **{kategorie}**.",
        "bewerbungskanal_ok": "Bewerbungen für {emoji} **{einheit}** landen in {kanal}.",
        "bewerbungskanal_weg": "{emoji} **{einheit}** nutzt wieder den allgemeinen Bewerbungs-Kanal.",
        "bewerbung_kategorie": "📨 Bewerbungen",
        "schon_da": "war schon eingerichtet",
        "bewerbung_kanalname": "bewerbung-{kurz}",
        "bewerbung_topic": "Bewerbungen für {einheit}",
        "bewerbungskanaele_titel": "Bewerbungs-Kanäle",
        "anzeigen_titel": "⚙️ Einrichtung",
        "check_titel": "🔍 Rollen-Check",
        "config_fehler": "config.yaml fehlerhaft: `{fehler}`",
        "config_ok": "Einstellungen neu geladen. (Änderungen an bot.py brauchen einen Neustart.)",
    },

    # ----------------------------------------------------------------------
    #  ALLGEMEIN (Fehlermeldungen, Embeds, Panels)
    # ----------------------------------------------------------------------
    "allgemein": {
        "titel_ok": "Erledigt",
        "titel_fehler": "Fehler",
        "titel_hinweis": "Hinweis",
        "nur_server": "Dieser Befehl geht nur auf dem Server.",
        "fehler_rechte": "Mir fehlen Rechte dafür. Prüfe, ob meine Bot-Rolle **über** den Rollen steht, die ich vergeben/entfernen soll, und ob ich die nötigen Berechtigungen habe.",
        "fehler_unerwartet": "Unerwarteter Fehler: `{fehler}`",
        "fehlende_rollen": "⚠️ Fehlende Rollen: {rollen}",
        "panel_gepostet": "Panel in {kanal} gepostet.",
        "keine": "Keine.",
        "nicht_gefunden": "Nicht gefunden.",
        "datum_ungueltig": "Ungültiges Datum.",
        "senden_fehler": "Senden fehlgeschlagen: {fehler}",
        "datum_beispiel": "Ungültiges Datum, z. B. `24.12.2026 18:00`.",
        "modal_ankuendigung": "Ankündigung erstellen",
        "modal_embed": "Embed erstellen",
        "feld_titel": "Titel",
        "feld_text": "Text",
        "feld_farbe": "Farbe (Hex, z. B. #4E5B31)",
        "feld_bild": "Bild-URL (optional)",
        "feld_fusszeile": "Fußzeile (optional)",
        "gesendet": "Gesendet.",
    },

    # ----------------------------------------------------------------------
    #  HILFE-BEFEHL
    # ----------------------------------------------------------------------
    "hilfe": {
        "text": "Alle Befehle, die **du** nutzen darfst:",
        "titel": "📖 Hilfe",
        "allgemein": "⭐ Allgemein",
    },

    # ----------------------------------------------------------------------
    #  UMFRAGE
    # ----------------------------------------------------------------------
    "umfrage": {
        "titel": "📊 {frage}",
        "emoji_ja": "👍",
        "emoji_nein": "👎",
    },

    # ----------------------------------------------------------------------
    #  SYMBOLE (Haken, Kreuz, Warnung ...)
    # ----------------------------------------------------------------------
    "symbole": {
        "ok": "✅",
        "fehler": "❌",
        "warnung": "⚠️",
        "ankuendigung": "📢",
        "ordner": "📁",
    },

    # ----------------------------------------------------------------------
    #  BEFEHLS-SYSTEM (Berechtigungs-/Cooldown-Meldungen)
    # ----------------------------------------------------------------------
    "befehle": {
        "nicht_gefunden": "Diesen Befehl gibt es nicht.",
        "name_laenge": "Name muss 1–32 Zeichen lang sein.",
        "name_ungueltig": "Slash-Befehle dürfen nur Kleinbuchstaben, Zahlen, `-` und `_` enthalten (max. 32 Zeichen, keine Leerzeichen).",
        "name_vergeben": "Der Name `{name}` ist schon vergeben (von `{key}`).",
        "name_custom": "`{name}` ist bereits ein eigener Befehl.",
        "deaktiviert": "Dieser Befehl ist deaktiviert.",
        "rolle_fehlt": "Dir fehlt eine der berechtigten Rollen für diesen Befehl.",
        "stufe_fehlt": "Dafür brauchst du die Berechtigungsstufe **{stufe}**.",
        "keine_berechtigung_titel": "Keine Berechtigung",
        "cooldown_text": "Bitte warte noch **{sekunden}s**.",
        "cooldown_titel": "Cooldown",
    },

    # ----------------------------------------------------------------------
    #  PING
    # ----------------------------------------------------------------------
    "ping": {
        "text": "Latenz: **{ms} ms**\nOnline seit: **{online}**",
        "titel": "🏓 Pong",
    },

    # ----------------------------------------------------------------------
    #  SERVERINFO
    # ----------------------------------------------------------------------
    "serverinfo": {
        "titel": "🏰 {server}",
        "mitglieder": "Mitglieder",
        "soldaten": "Aktive Soldaten",
        "im_dienst": "Im Dienst",
        "rollen": "Rollen",
        "kanaele": "Kanäle",
        "boosts": "Boosts",
        "inhaber": "Inhaber",
        "erstellt": "Erstellt",
    },

    # ----------------------------------------------------------------------
    #  USERINFO
    # ----------------------------------------------------------------------
    "userinfo": {
        "titel": "👤 {name}",
        "erstellt": "Account erstellt",
        "beigetreten": "Beigetreten",
        "einheiten": "Einheiten",
        "rollen": "Rollen ({anzahl})",
    },

    # ----------------------------------------------------------------------
    #  AVATAR
    # ----------------------------------------------------------------------
    "avatar": {
        "titel": "🖼️ {name}",
    },
}


def load_config() -> dict:
    return yaml.safe_load(CONFIG_YAML) or {}


# ==========================================================================
#  TEXTE & PINGS – T("schlüssel", "Standardtext") und P("schlüssel", guild)
#  T("schlüssel", "Standardtext") liefert den Text (siehe TEXTE in den EINSTELLUNGEN zum Überschreiben).
#  P("schlüssel", guild) liefert die Pings aus PINGS in den EINSTELLUNGEN.
# ==========================================================================

_TEXTE: dict = {}
_PINGS: dict = {}


class _Leer(dict):
    def __missing__(self, key):  # unbekannte Platzhalter bleiben stehen
        return "{" + key + "}"


def setze_daten(texte: dict | None, pings: dict | None) -> None:
    global _TEXTE, _PINGS
    _TEXTE = texte or {}
    _PINGS = pings or {}


def _hole(key: str):
    node: Any = _TEXTE
    for teil in key.split("."):
        if not isinstance(node, dict) or teil not in node:
            return None
        node = node[teil]
    return node


def T(key: str, default: str = "", **werte) -> str:
    wert = _hole(key)
    text = default if wert is None else str(wert).rstrip("\n")
    if werte:
        try:
            text = text.format_map(_Leer(werte))
        except (ValueError, IndexError):
            pass
    return text


def P(key: str, guild, *extra) -> str | None:
    """Erwähnungen der in pings:<key> eingetragenen Rollen (+ optionale extra Rollen/Strings)."""
    teile = [x for x in [P_liste(_PINGS.get(key), guild), *[getattr(e, "mention", e) for e in extra if e]] if x]
    return " ".join(dict.fromkeys(" ".join(teile).split())) or None


def P_liste(eintraege, guild) -> str | None:
    if not eintraege:
        return None
    if isinstance(eintraege, (str, int)):
        eintraege = [eintraege]
    teile = []
    for e in eintraege:
        e = str(e).strip()
        if e.lower() in ("everyone", "@everyone"):
            teile.append("@everyone")
        elif e.lower() in ("here", "@here"):
            teile.append("@here")
        elif e.isdigit():
            teile.append(f"<@&{e}>")
        elif guild is not None:
            rolle = next((r for r in guild.roles if r.name == e), None)
            if rolle:
                teile.append(rolle.mention)
            else:
                log.warning("Ping-Rolle '%s' nicht gefunden", e)
    return " ".join(teile) or None


def scanne_code(ordner: Path) -> tuple[dict[str, str], list[str]]:
    """Findet alle T("key", "default") und P("key", ...) Aufrufe im Code."""
    texte: dict[str, str] = {}
    pings: list[str] = []
    for datei in sorted(ordner.rglob("*.py")):
        try:
            baum = ast.parse(datei.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(baum):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            a0 = node.args[0]
            if not (isinstance(a0, ast.Constant) and isinstance(a0.value, str)):
                continue
            if name == "T" and len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                texte.setdefault(a0.value, node.args[1].value)
            elif name == "P" and a0.value not in pings:
                pings.append(a0.value)
    # Reihenfolge: nach Bereich gruppieren, innerhalb in Code-Reihenfolge
    return texte, pings


setze_daten(TEXTE, PINGS)   # Texte aus dem Abschnitt TEXTE und Pings aus PINGS aktivieren


# ==========================================================================
#  HELFER – Embeds, Farben, Zeitstempel, DM
# ==========================================================================

TZ = ZoneInfo("Europe/Berlin")

# Werden beim Start aus der config.yaml gesetzt
FARBE = discord.Color.from_rgb(78, 91, 49)
FOOTER = "Bundeswehr Roleplay"
GRUEN = discord.Color.from_rgb(46, 160, 67)
ROT = discord.Color.from_rgb(218, 54, 51)
GELB = discord.Color.from_rgb(219, 171, 9)


def branding(name: str, farbe: str | None) -> None:
    global FARBE, FOOTER
    FOOTER = name
    if farbe:
        FARBE = discord.Color.from_str(farbe)


def now() -> int:
    return int(time.time())


def embed(title: str | None = None, desc: str | None = None,
          color: discord.Color | None = None) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color or FARBE,
                      timestamp=discord.utils.utcnow())
    e.set_footer(text=FOOTER)
    return e


def ok(text: str, title: str | None = None) -> discord.Embed:
    return embed(f"{T('symbole.ok', '✅')} {title or T('allgemein.titel_ok', 'Erledigt')}", text, GRUEN)


def fehler(text: str, title: str | None = None) -> discord.Embed:
    return embed(f"{T('symbole.fehler', '❌')} {title or T('allgemein.titel_fehler', 'Fehler')}", text, ROT)


def warnung(text: str, title: str | None = None) -> discord.Embed:
    return embed(f"{T('symbole.warnung', '⚠️')} {title or T('allgemein.titel_hinweis', 'Hinweis')}", text, GELB)


def ts(unix: int | float | None, style: str = "f") -> str:
    if not unix:
        return "–"
    return f"<t:{int(unix)}:{style}>"


_DAUER_RE = re.compile(r"(\d+)\s*(w|d|t|h|std|m|min|s)", re.I)
_FAKTOR = {"w": 604800, "d": 86400, "t": 86400, "h": 3600, "std": 3600,
           "m": 60, "min": 60, "s": 1}


def parse_dauer(text: str) -> int | None:
    """'1h30m', '2d', '45min' -> Sekunden"""
    total = 0
    for zahl, einheit in _DAUER_RE.findall(text or ""):
        total += int(zahl) * _FAKTOR[einheit.lower()]
    return total or None


def fmt_dauer(sek: int | float) -> str:
    sek = int(sek)
    d, r = divmod(sek, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    teile = []
    if d:
        teile.append(f"{d}T")
    if h:
        teile.append(f"{h}h")
    teile.append(f"{m}m")
    return " ".join(teile)


def parse_datum(text: str) -> dt.datetime | None:
    """Akzeptiert '24.12.2026 18:00', '24.12.2026', '24.12. 18:00', '18:00' (heute)."""
    text = (text or "").strip()
    jetzt = dt.datetime.now(TZ)
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%y %H:%M", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=TZ)
        except ValueError:
            pass
    for fmt in ("%d.%m. %H:%M", "%d.%m %H:%M", "%d.%m.", "%d.%m"):
        try:
            d = dt.datetime.strptime(text, fmt)
            return d.replace(year=jetzt.year, tzinfo=TZ)
        except ValueError:
            pass
    try:
        t = dt.datetime.strptime(text, "%H:%M")
        return jetzt.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    except ValueError:
        return None


def chunk_lines(lines: Iterable[str], limit: int = 3900) -> list[str]:
    chunks, cur = [], ""
    for line in lines:
        if len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur:
        chunks.append(cur)
    return chunks or ["–"]


async def send_log(bot, guild: discord.Guild, art: str, e: discord.Embed,
                   file: discord.File | None = None, content: str | None = None) -> None:
    """Schickt ein Log-Embed in den Kanal 'kanal_<art>' (Fallback: allgemeiner Log-Kanal)."""
    cid = await bot.db.get_setting(guild.id, f"kanal_{art}") or await bot.db.get_setting(guild.id, "kanal_log")
    if not cid:
        return
    ch = guild.get_channel(int(cid))
    if ch is None:
        return
    try:
        am = discord.AllowedMentions(roles=True, everyone=True, users=True)
        if file:
            await ch.send(content=content, embed=e, file=file, allowed_mentions=am)
        else:
            await ch.send(content=content, embed=e, allowed_mentions=am)
    except discord.HTTPException:
        pass


async def dm(user: discord.abc.User, e: discord.Embed) -> bool:
    try:
        await user.send(embed=e)
        return True
    except discord.HTTPException:
        return False


def kann_moderieren(actor: discord.Member, ziel: discord.Member) -> bool:
    if actor.guild.owner_id == actor.id:
        return True
    if ziel.guild.owner_id == ziel.id:
        return False
    return actor.top_role > ziel.top_role


# ==========================================================================
#  RECHTE – Berechtigungsstufen, Einheiten, Dienstgrade (aus EINSTELLUNGEN)
# ==========================================================================

@dataclass
class Position:
    titel: str
    rolle: str


@dataclass
class Einheit:
    name: str
    kurz: str
    positionen: list[Position] = field(default_factory=list)
    emoji: str = "🎖️"


@dataclass
class Dienstgrad:
    name: str
    kurz: str
    gruppe: str = ""


class Rechte:
    """Berechtigungsstufen, Einheiten und Dienstgrade aus der config.yaml."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self.reload()

    # ------------------------------------------------------------------ Laden
    def reload(self) -> None:
        cfg = self.bot.cfg
        self.stufen_cfg: dict = cfg.get("berechtigungen", {}) or {}
        pers = cfg.get("personal", {}) or {}
        self.verwalten_ab: int = int(pers.get("verwalten_ab_position", 5))
        self.basis_position: int = int(pers.get("basis_position", 1))
        self.global_stufen: list[str] = pers.get("global_stufen", ["admin"])
        self.zusatzrollen: list[str] = pers.get("zusatzrollen", [])

        vorlage = cfg.get("positionen_vorlage", [])
        self.einheiten: dict[str, Einheit] = {}
        for e in cfg.get("einheiten", []):
            roh = e.get("positionen") or vorlage
            positionen = [Position(p["titel"], p["rolle"].format(einheit=e["name"])) for p in roh]
            self.einheiten[e["name"]] = Einheit(e["name"], e.get("kurz", e["name"][:4]),
                                                positionen, e.get("emoji", "🎖️"))

        self.dienstgrade: list[Dienstgrad] = [
            Dienstgrad(d["name"], d.get("kurz", d["name"]), d.get("gruppe", ""))
            for d in cfg.get("dienstgrade", [])
        ]

    # --------------------------------------------------------------- Einheiten
    def einheit(self, name: str | None) -> Einheit | None:
        if not name:
            return None
        n = name.lower().strip()
        for e in self.einheiten.values():
            if e.name.lower() == n or e.kurz.lower() == n:
                return e
        return None

    def position_von(self, member: discord.Member, einheit: Einheit) -> int:
        namen = {r.name for r in member.roles}
        best = -1
        for i, p in enumerate(einheit.positionen):
            if p.rolle in namen:
                best = i
        return best

    def einheiten_von(self, member: discord.Member) -> list[tuple[Einheit, int]]:
        out = []
        for e in self.einheiten.values():
            p = self.position_von(member, e)
            if p >= 0:
                out.append((e, p))
        return out

    def ist_global(self, member: discord.Member) -> bool:
        return any(self.hat_stufe(member, s) for s in self.global_stufen)

    def verwaltung(self, member: discord.Member, einheit: Einheit) -> int:
        """Gibt zurück, bis zu welcher Position (exklusiv) der Member in dieser Einheit
        Positionen vergeben darf. -1 = gar nicht."""
        if self.ist_global(member):
            return len(einheit.positionen)
        pos = self.position_von(member, einheit)
        if pos >= self.verwalten_ab:
            return pos
        return -1

    # ------------------------------------------------------------------ Stufen
    def stufen(self) -> list[str]:
        return ["jeder", *self.stufen_cfg.keys()]

    def hat_stufe(self, member: discord.abc.User, stufe: str | None,
                  _seen: set | None = None) -> bool:
        if stufe in (None, "", "jeder"):
            return True
        if not isinstance(member, discord.Member):
            return False
        if member.guild_permissions.administrator:
            return True
        conf = self.stufen_cfg.get(stufe)
        if not conf:
            return False
        _seen = _seen or set()
        _seen.add(stufe)
        namen = {r.name for r in member.roles}
        if any(n in namen for n in conf.get("rollen", []) or []):
            return True
        ab = conf.get("einheit_ab_position")
        if ab is not None:
            for e in self.einheiten.values():
                if self.position_von(member, e) >= int(ab):
                    return True
        for p in conf.get("plus", []) or []:
            if p not in _seen and self.hat_stufe(member, p, _seen):
                return True
        return False

    def rollen_namen_fuer_stufe(self, stufe: str, _seen: set | None = None) -> set[str]:
        conf = self.stufen_cfg.get(stufe) or {}
        _seen = _seen or set()
        _seen.add(stufe)
        namen = set(conf.get("rollen", []) or [])
        for p in conf.get("plus", []) or []:
            if p not in _seen:
                namen |= self.rollen_namen_fuer_stufe(p, _seen)
        return namen

    def rollen_fuer_stufe(self, guild: discord.Guild, stufe: str) -> list[discord.Role]:
        return [r for n in self.rollen_namen_fuer_stufe(stufe) if (r := self.rolle(guild, n))]

    # ------------------------------------------------------------------- Rollen
    @staticmethod
    def rolle(guild: discord.Guild, name: str) -> discord.Role | None:
        return discord.utils.get(guild.roles, name=name)

    def alle_rollen_namen(self) -> set[str]:
        namen = set(self.zusatzrollen)
        for conf in self.stufen_cfg.values():
            namen |= set(conf.get("rollen", []) or [])
        for e in self.einheiten.values():
            namen |= {p.rolle for p in e.positionen}
        return namen


# ==========================================================================
#  DATENBANK (SQLite)
# ==========================================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (guild_id, key));

CREATE TABLE IF NOT EXISTS soldaten (
    guild_id INTEGER, user_id INTEGER, einheit TEXT, position INTEGER DEFAULT 0,
    dienstgrad INTEGER DEFAULT 0, rp_name TEXT, eintritt INTEGER,
    status TEXT DEFAULT 'aktiv', PRIMARY KEY (guild_id, user_id));

CREATE TABLE IF NOT EXISTS personal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    aktion TEXT, details TEXT, von INTEGER, zeit INTEGER);

CREATE TABLE IF NOT EXISTS notizen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    text TEXT, von INTEGER, zeit INTEGER);

CREATE TABLE IF NOT EXISTS lehrgaenge (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    lehrgang TEXT, ausbilder INTEGER, zeit INTEGER,
    UNIQUE (guild_id, user_id, lehrgang));

CREATE TABLE IF NOT EXISTS warns (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    grund TEXT, von INTEGER, zeit INTEGER);

CREATE TABLE IF NOT EXISTS dienst (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    start INTEGER, ende INTEGER);

CREATE TABLE IF NOT EXISTS abmeldungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    von INTEGER, bis INTEGER, grund TEXT, zeit INTEGER, aktiv INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS bewerbungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    einheit TEXT, antworten TEXT, status TEXT DEFAULT 'offen',
    bearbeiter INTEGER, grund TEXT, zeit INTEGER);

CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY, guild_id INTEGER, user_id INTEGER, art TEXT,
    nummer INTEGER, uebernommen INTEGER, offen INTEGER DEFAULT 1, zeit INTEGER);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, channel_id INTEGER,
    message_id INTEGER, art TEXT, titel TEXT, beschreibung TEXT, ort TEXT,
    zeitpunkt INTEGER, ersteller INTEGER, erinnert INTEGER DEFAULT 0,
    aktiv INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS event_teilnehmer (
    event_id INTEGER, user_id INTEGER, status TEXT, PRIMARY KEY (event_id, user_id));

CREATE TABLE IF NOT EXISTS appelle (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, channel_id INTEGER,
    message_id INTEGER, titel TEXT, rolle_id INTEGER, ende INTEGER,
    ersteller INTEGER, aktiv INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS appell_anwesend (
    appell_id INTEGER, user_id INTEGER, zeit INTEGER, PRIMARY KEY (appell_id, user_id));

CREATE TABLE IF NOT EXISTS custom_commands (
    guild_id INTEGER, name TEXT, beschreibung TEXT, antwort TEXT,
    embed INTEGER DEFAULT 1, privat INTEGER DEFAULT 0, stufe TEXT DEFAULT 'jeder',
    ersteller INTEGER, zeit INTEGER, PRIMARY KEY (guild_id, name));
"""


class Database:
    def __init__(self, path) -> None:
        self.path = str(path)
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def execute(self, query: str, *params: Any) -> int:
        cur = await self.conn.execute(query, params)
        await self.conn.commit()
        return cur.lastrowid

    async def fetchone(self, query: str, *params: Any):
        cur = await self.conn.execute(query, params)
        return await cur.fetchone()

    async def fetchall(self, query: str, *params: Any):
        cur = await self.conn.execute(query, params)
        return await cur.fetchall()

    # ---------- Einstellungen ----------
    async def get_setting(self, guild_id: int, key: str, default: Any = None):
        row = await self.fetchone(
            "SELECT value FROM settings WHERE guild_id=? AND key=?", guild_id, key
        )
        return row["value"] if row else default

    async def set_setting(self, guild_id: int, key: str, value: Any) -> None:
        if value is None:
            await self.execute("DELETE FROM settings WHERE guild_id=? AND key=?", guild_id, key)
        else:
            await self.execute(
                "INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?,?,?)",
                guild_id, key, str(value),
            )

    async def all_settings(self, guild_id: int) -> dict[str, str]:
        rows = await self.fetchall("SELECT key, value FROM settings WHERE guild_id=?", guild_id)
        return {r["key"]: r["value"] for r in rows}


# ==========================================================================
#  CHECKS – @stufe("...") für Befehle
#  Decorator, um einem Slash-Befehl eine Standard-Berechtigungsstufe zu geben.
#
#  Beispiel:
#      @stufe("moderator")
#      @app_commands.command(...)
#      async def ban(...): ...
#
#  Die Stufen sind in der config.yaml unter 'berechtigungen' definiert und können
#  pro Befehl über /befehle rechte bzw. /befehle rollen überschrieben werden.
# ==========================================================================

def stufe(name: str):
    def deco(cmd):
        cmd.extras["perm"] = name
        return cmd
    return deco


# ==========================================================================
#  AUTOCOMPLETE – Vorschläge in Slash-Befehlen
# ==========================================================================

async def einheit(interaction: discord.Interaction, current: str):
    cur = current.lower()
    return [app_commands.Choice(name=f"{e.name} ({e.kurz})", value=e.name)
            for e in interaction.client.rechte.einheiten.values()
            if cur in e.name.lower() or cur in e.kurz.lower()][:25]


async def position(interaction: discord.Interaction, current: str):
    bot = interaction.client
    r = bot.rechte
    ns = interaction.namespace
    e = r.einheit(getattr(ns, "einheit", None))
    if e is None:
        user = getattr(ns, "user", None)
        if user is not None:
            row = await bot.db.fetchone("SELECT einheit FROM soldaten WHERE guild_id=? AND user_id=? AND status='aktiv'",
                                        interaction.guild_id, user.id)
            if row:
                e = r.einheit(row["einheit"])
    if e is None:
        return []
    return [app_commands.Choice(name=f"{i} · {p.titel}", value=i)
            for i, p in enumerate(e.positionen) if current.lower() in p.titel.lower()][:25]


async def dienstgrad(interaction: discord.Interaction, current: str):
    cur = current.lower()
    return [app_commands.Choice(name=f"{d.name} ({d.kurz})", value=i)
            for i, d in enumerate(interaction.client.rechte.dienstgrade)
            if cur in d.name.lower() or cur in d.kurz.lower()][:25]


async def lehrgang(interaction: discord.Interaction, current: str):
    liste = interaction.client.cfg.get("ausbildung", {}).get("lehrgaenge", [])
    return [app_commands.Choice(name=l, value=l) for l in liste if current.lower() in l.lower()][:25]


# ==========================================================================
#  BEFEHLS-MANAGER – registriert alle Slash-Befehle und synchronisiert sie mit Discord
# ==========================================================================

NAME_RE = re.compile(r"^[-_\w]{1,32}$")
GESCHUETZT = ("befehle",)  # kann nicht deaktiviert werden (sonst sperrst du dich aus)
FELDER = ("name", "beschreibung", "aktiv", "stufe", "rollen", "cooldown")




def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def _wert(v):
    if isinstance(v, str) and "\n" in v:
        return LiteralScalarString(v)
    return v


class CommandManager:
    def __init__(self, bot) -> None:
        self.bot = bot
        self.doc: CommentedMap = CommentedMap()
        self.registry: list = []
        self.custom: dict[str, app_commands.Command] = {}
        self._cooldowns: dict[tuple[str, int], float] = {}
        self.load()

    # ================================================================ Datei
    def load(self) -> None:
        """Texte & Pings kommen jetzt direkt aus dem Code (T(...)) und den EINSTELLUNGEN ganz oben (PINGS, TEXTE)."""
        for sek in ("befehle", "eigene_befehle", "pings", "texte"):
            if not isinstance(self.doc.get(sek), dict):
                self.doc[sek] = CommentedMap()
        tx.setze_daten(TEXTE, PINGS)

    def save(self) -> None:
        """Es gibt keine befehle.yaml mehr – alles steht in dieser Datei."""
        return None

    @property
    def cmds(self) -> CommentedMap:
        return self.doc["befehle"]

    # ============================================================ Registry
    def capture(self) -> None:
        """Merkt sich alle Befehle im Originalzustand und bereitet sie für Discord vor."""
        self.registry = list(self.bot.tree.get_commands())
        for c in self.registry:
            self._tag(c, None)
        for key, c, _, _ in self.walk():
            self._eintrag(key, c)
        self.save()

    def _tag(self, c, parent_key: str | None) -> None:
        key = c.name if parent_key is None else f"{parent_key} {c.name}"
        c.extras["key"] = key
        c.extras["orig_name"] = c.name
        c.extras["orig_desc"] = getattr(c, "description", None)
        if isinstance(c, app_commands.Group):
            kids = list(c.commands)
            c.extras["orig_children"] = kids
            for k in kids:
                self._tag(k, key)

    def _standard(self, c, feld: str):
        gruppe = isinstance(c, app_commands.Group)
        return {
            "name": c.extras["orig_name"],
            "beschreibung": c.extras.get("orig_desc") if not isinstance(c, app_commands.ContextMenu) else None,
            "aktiv": True,
            "stufe": None if gruppe else c.extras.get("perm", "jeder"),
            "rollen": [],
            "cooldown": 0,
        }[feld]

    def _eintrag(self, key: str, c) -> CommentedMap:
        e = self.cmds.get(key)
        if not isinstance(e, dict):
            e = CommentedMap()
            self.cmds[key] = e
        for f in FELDER:
            if f not in e:
                if f == "beschreibung" and isinstance(c, app_commands.ContextMenu):
                    continue
                e[f] = self._standard(c, f)
        return e

    def walk(self) -> Iterator[tuple[str, object, str, bool]]:
        """(schlüssel, befehl, aktueller_pfad, aktiv) für alle Befehle."""
        def rec(c, pfad_parent: str, aktiv_parent: bool):
            key = c.extras["key"]
            ov = self.ov(key)
            name = self._name(c, ov)
            pfad = f"{pfad_parent} {name}".strip()
            aktiv = aktiv_parent and ov.get("aktiv", True) is not False
            yield key, c, pfad, aktiv
            for k in c.extras.get("orig_children", []):
                yield from rec(k, pfad, aktiv)
        for c in self.registry:
            yield from rec(c, "", True)

    def _name(self, c, ov: dict) -> str:
        name = str(ov.get("name") or c.extras["orig_name"]).strip()
        if isinstance(c, app_commands.ContextMenu):
            return name[:32] or c.extras["orig_name"]
        name = name.lower()
        if not NAME_RE.match(name):
            log.warning("Ungültiger Name '%s' für %s – Originalname wird genutzt", name, c.extras["key"])
            return c.extras["orig_name"]
        return name

    def finde(self, key: str):
        for k, c, _, _ in self.walk():
            if k == key:
                return c
        return None

    def ov(self, key: str | None) -> dict:
        e = self.cmds.get(key or "")
        return e if isinstance(e, dict) else {}

    def setze(self, key: str, **werte) -> None:
        c = self.finde(key)
        e = self._eintrag(key, c)
        for k, v in werte.items():
            e[k] = self._standard(c, k) if v is None else _wert(v)
        self.save()

    def reset(self, key: str | None = None) -> None:
        keys = [key] if key else [k for k, *_ in self.walk()]
        for k in keys:
            c = self.finde(k)
            if c is None:
                continue
            e = self._eintrag(k, c)
            for f in list(e.keys()):
                if f in FELDER:
                    e[f] = self._standard(c, f)
        self.save()

    # ------------------------------------------------------ Umbenennen-Check
    def pruefe_name(self, key: str, neu: str) -> str | None:
        c = self.finde(key)
        if c is None:
            return T("befehle.nicht_gefunden", "Diesen Befehl gibt es nicht.")
        if isinstance(c, app_commands.ContextMenu):
            if not 1 <= len(neu) <= 32:
                return T("befehle.name_laenge", "Name muss 1–32 Zeichen lang sein.")
        elif not NAME_RE.match(neu) or neu != neu.lower():
            return T("befehle.name_ungueltig", "Slash-Befehle dürfen nur Kleinbuchstaben, Zahlen, `-` und `_` enthalten (max. 32 Zeichen, keine Leerzeichen).")
        parent = getattr(c, "parent", None)
        if parent is not None:
            geschwister = parent.extras.get("orig_children", [])
        else:
            ctx = isinstance(c, app_commands.ContextMenu)
            geschwister = [x for x in self.registry
                           if isinstance(x, app_commands.ContextMenu) == ctx and (not ctx or x.type == c.type)]
        for g in geschwister:
            if g is not c and self._name(g, self.ov(g.extras["key"])) == neu:
                return T("befehle.name_vergeben", "Der Name `{name}` ist schon vergeben (von `{key}`).",
                         name=neu, key=g.extras["key"])
        if parent is None and neu in self.custom:
            return T("befehle.name_custom", "`{name}` ist bereits ein eigener Befehl.", name=neu)
        return None

    # =============================================================== Aufbau
    def _build(self, c) -> bool:
        key = c.extras["key"]
        ov = self.ov(key)
        if ov.get("aktiv") is False and not key.startswith(GESCHUETZT):
            return False
        c.name = self._name(c, ov)
        if not isinstance(c, app_commands.ContextMenu):
            c.description = str(ov.get("beschreibung") or c.extras["orig_desc"] or "–")[:100]
        if isinstance(c, app_commands.Group):
            for kid in list(c.commands):
                c.remove_command(kid.name)
            kids = [k for k in c.extras["orig_children"] if self._build(k)]
            if not kids:
                return False
            for k in kids:
                try:
                    c.add_command(k)
                except app_commands.CommandAlreadyRegistered:
                    log.error("Doppelter Name '%s' in Gruppe %s – Originalname wird genutzt", k.name, key)
                    k.name = k.extras["orig_name"]
                    c.add_command(k, override=True)
        return True

    def apply(self) -> None:
        tree = self.bot.tree
        tree.clear_commands(guild=None)
        for c in self.registry:
            if not self._build(c):
                continue
            try:
                tree.add_command(c)
            except app_commands.CommandAlreadyRegistered:
                log.error("Doppelter Name '%s' – Originalname wird genutzt", c.name)
                c.name = c.extras["orig_name"]
                tree.add_command(c, override=True)

    async def sync(self) -> list:
        self.apply()
        self.lade_custom()
        tree = self.bot.tree
        gid = self.bot.guild_id
        belegt = {c.name for c in tree.get_commands(type=discord.AppCommandType.chat_input)}
        if gid:
            guild = discord.Object(id=gid)
            tree.clear_commands(guild=guild)
            tree.copy_global_to(guild=guild)
            for name, cmd in self.custom.items():
                if name not in belegt:
                    tree.add_command(cmd, guild=guild, override=True)
            return await tree.sync(guild=guild)
        for name, cmd in self.custom.items():
            if name not in belegt:
                tree.add_command(cmd, override=True)
        return await tree.sync()

    async def neuladen(self) -> list:
        """Befehle neu synchronisieren."""
        self.load()
        for key, c, _, _ in self.walk():
            self._eintrag(key, c)
        self.save()
        return await self.sync()

    # ======================================================= Eigene Befehle
    @property
    def eigene(self) -> CommentedMap:
        return self.doc["eigene_befehle"]

    def lade_custom(self) -> None:
        self.custom.clear()
        for name, data in self.eigene.items():
            name = str(name).lower()
            if not NAME_RE.match(name) or not isinstance(data, dict):
                log.warning("Eigener Befehl '%s' ungültig – übersprungen", name)
                continue
            if data.get("aktiv", True) is False:
                continue
            self.custom[name] = self._make_custom(name, data)

    def _make_custom(self, name: str, data: dict) -> app_commands.Command:
        mgr = self

        async def callback(interaction: discord.Interaction) -> None:
            d = mgr.eigene.get(name) or {}
            text = formatiere(str(d.get("antwort", "")), interaction)
            ping = tx.P_liste(d.get("ping"), interaction.guild)
            privat = bool(d.get("privat"))
            am = discord.AllowedMentions(roles=True, everyone=True)
            if d.get("embed", True):
                e = u.embed(d.get("titel") or None, text[:4000])
                if d.get("bild"):
                    e.set_image(url=d["bild"])
                await interaction.response.send_message(content=ping, embed=e, ephemeral=privat, allowed_mentions=am)
            else:
                await interaction.response.send_message(((ping + "\n") if ping else "") + text[:1900],
                                                        ephemeral=privat, allowed_mentions=am)

        cmd = app_commands.Command(name=name, description=str(data.get("beschreibung") or "Eigener Befehl")[:100],
                                   callback=callback)
        cmd.guild_only = True
        cmd.extras.update(key=f"eigen:{name}", perm=data.get("stufe") or "jeder", custom=True,
                          orig_name=name, orig_desc=cmd.description)
        return cmd

    # ============================================================== Prüfung
    def _kette(self, cmd) -> list:
        kette, c = [], cmd
        while c is not None:
            kette.append(c)
            c = getattr(c, "parent", None)
        return kette  # [blatt, ..., gruppe]

    def _ov_cmd(self, c) -> dict:
        if c.extras.get("custom"):
            d = self.eigene.get(c.extras["orig_name"]) or {}
            return {"stufe": d.get("stufe") or "jeder", "rollen": d.get("rollen") or [],
                    "cooldown": d.get("cooldown") or 0}
        return self.ov(c.extras.get("key"))

    def erlaubt(self, member: discord.Member, cmd) -> tuple[bool, str | None]:
        kette = self._kette(cmd)
        for c in kette:
            k = c.extras.get("key", "")
            if self.ov(k).get("aktiv") is False and not k.startswith(GESCHUETZT):
                return False, T("befehle.deaktiviert", "Dieser Befehl ist deaktiviert.")
        if not isinstance(member, discord.Member):
            return False, T("allgemein.nur_server", "Dieser Befehl geht nur auf dem Server.")
        r = self.bot.rechte
        if member.guild_permissions.administrator or r.hat_stufe(member, "admin"):
            return True, None

        # Gruppe zuerst: was bei der Gruppe gesetzt ist, gilt für alle Unterbefehle
        rollen, stufe = None, None
        for c in reversed(kette):
            ov = self._ov_cmd(c)
            if rollen is None and ov.get("rollen"):
                rollen = ov["rollen"]
            if stufe is None and ov.get("stufe"):
                stufe = ov["stufe"]
        if stufe is None:
            stufe = next((c.extras["perm"] for c in kette if c.extras.get("perm")), "jeder")

        if rollen:
            ziel = {str(x).strip() for x in rollen}
            if any(str(x.id) in ziel or x.name in ziel for x in member.roles):
                return True, None
            return False, T("befehle.rolle_fehlt", "Dir fehlt eine der berechtigten Rollen für diesen Befehl.")
        if not r.hat_stufe(member, stufe):
            return False, T("befehle.stufe_fehlt", "Dafür brauchst du die Berechtigungsstufe **{stufe}**.", stufe=stufe)
        return True, None

    def cooldown(self, member: discord.Member, cmd) -> float:
        if member.guild_permissions.administrator:
            return 0
        for c in self._kette(cmd):
            key = c.extras.get("key", "")
            sek = self._ov_cmd(c).get("cooldown")
            if sek:
                jetzt = time.monotonic()
                bis = self._cooldowns.get((key, member.id), 0)
                if bis > jetzt:
                    return bis - jetzt
                self._cooldowns[(key, member.id)] = jetzt + float(sek)
                return 0
        return 0


def formatiere(text: str, interaction: discord.Interaction) -> str:
    g = interaction.guild
    ersatz = {
        "{user}": interaction.user.mention,
        "{user_name}": interaction.user.display_name,
        "{server}": g.name if g else "",
        "{mitglieder}": str(g.member_count if g else 0),
        "{kanal}": interaction.channel.mention if interaction.channel else "",
    }
    for k, v in ersatz.items():
        text = text.replace(k, v)
    return text.replace("\\n", "\n")


class BwTree(app_commands.CommandTree):
    """Prüft vor jedem Befehl Status, Berechtigung und Cooldown."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cmd = interaction.command
        mgr: CommandManager | None = getattr(self.client, "cmd_manager", None)
        if cmd is None or mgr is None:
            return True
        ok, msg = mgr.erlaubt(interaction.user, cmd)
        is_cmd = interaction.type == discord.InteractionType.application_command
        if not ok:
            if is_cmd:
                await interaction.response.send_message(
                    embed=u.fehler(msg, T("befehle.keine_berechtigung_titel", "Keine Berechtigung")), ephemeral=True)
            return False
        if is_cmd:
            rest = mgr.cooldown(interaction.user, cmd)
            if rest:
                await interaction.response.send_message(embed=u.warnung(
                    T("befehle.cooldown_text", "Bitte warte noch **{sekunden}s**.", sekunden=int(rest) + 1),
                    T("befehle.cooldown_titel", "Cooldown")), ephemeral=True)
                return False
        return True

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        original = getattr(error, "original", error)
        if isinstance(original, discord.Forbidden):
            text = T("allgemein.fehler_rechte", "Mir fehlen Rechte dafür. Prüfe, ob meine Bot-Rolle **über** den Rollen steht, "
                     "die ich vergeben/entfernen soll, und ob ich die nötigen Berechtigungen habe.")
        elif isinstance(error, app_commands.CheckFailure):
            text = str(error) or T("befehle.keine_berechtigung_titel", "Keine Berechtigung")
        else:
            log.exception("Fehler in /%s", interaction.command.qualified_name if interaction.command else "?",
                          exc_info=original)
            text = T("allgemein.fehler_unerwartet", "Unerwarteter Fehler: `{fehler}`",
                     fehler=f"{type(original).__name__}: {original}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=u.fehler(text), ephemeral=True)
            else:
                await interaction.response.send_message(embed=u.fehler(text), ephemeral=True)
        except discord.HTTPException:
            pass


# ==========================================================================
#  BOT – Start, Module laden, Status
# ==========================================================================



class BwBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents,
                         tree_cls=BwTree, help_command=None)
        self.cfg = load_config()
        bot_cfg = self.cfg.get("bot", {})
        u.branding(bot_cfg.get("name", "Bundeswehr Roleplay"), bot_cfg.get("farbe"))
        self.db = Database(DATA / "bot.db")
        self.rechte = Rechte(self)
        self.cmd_manager = CommandManager(self)

    @property
    def guild_id(self) -> int | None:
        gid = self.cfg.get("bot", {}).get("guild_id")
        return int(gid) if gid else None

    def reload_config(self) -> None:
        self.cfg = load_config()
        bot_cfg = self.cfg.get("bot", {})
        u.branding(bot_cfg.get("name", "Bundeswehr Roleplay"), bot_cfg.get("farbe"))
        self.rechte.reload()
        self.cmd_manager.load()

    async def setup_hook(self) -> None:
        await self.db.connect()
        for cog in MODULE:
            await self.add_cog(cog(self))
            log.info("Modul geladen: %s", cog.__name__)
        self.cmd_manager.capture()
        synced = await self.cmd_manager.sync()
        log.info("%d Slash-Befehle synchronisiert", len(synced))

    async def on_ready(self) -> None:
        log.info("Eingeloggt als %s (%s)", self.user, self.user.id)
        status = self.cfg.get("bot", {}).get("status", "Bundeswehr Roleplay")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status))

    async def close(self) -> None:
        await self.db.close()
        await super().close()


# ==========================================================================
#  MODUL: SETUP – Kanäle/Kategorien einstellen, Rollen prüfen
#  /setup – Kanäle, Kategorien und Rollen-Check
# ==========================================================================

KANAL_TYPEN = {
    "log": "Allgemeiner Log (Fallback für alle Logs)",
    "personal": "Personal-Log (Einstellungen, Beförderungen …)",
    "mod": "Moderations-Log",
    "nachrichten": "Nachrichten-Log (gelöscht/bearbeitet)",
    "willkommen": "Willkommensnachrichten",
    "abschied": "Abschiedsnachrichten",
    "bewerbungen": "Eingang neuer Bewerbungen (für Karriere Center)",
    "ticket": "Ticket-Log (Transkripte)",
    "dienst": "Dienst-Log (Dienstbeginn/-ende)",
    "abmeldung": "Abmeldungen",
    "befoerderungen": "Öffentliche Beförderungs-Bekanntgaben",
    "events": "Standard-Kanal für Events",
}


class Setup(commands.Cog):
    setup_grp = app_commands.Group(name="setup", description="Bot einrichten", guild_only=True)

    def __init__(self, bot) -> None:
        self.bot = bot

    @stufe("admin")
    @setup_grp.command(name="kanal", description="Legt einen Kanal für eine Bot-Funktion fest")
    @app_commands.choices(typ=[app_commands.Choice(name=v[:100], value=k) for k, v in KANAL_TYPEN.items()])
    @app_commands.describe(kanal="Leer lassen zum Entfernen")
    async def kanal(self, interaction: discord.Interaction, typ: str,
                    kanal: discord.TextChannel | None = None) -> None:
        await self.bot.db.set_setting(interaction.guild_id, f"kanal_{typ}", kanal.id if kanal else None)
        txt = T("setup.kanal_gesetzt", "**{typ}** → {kanal}", typ=KANAL_TYPEN[typ], kanal=kanal.mention) if kanal \
            else T("setup.kanal_entfernt", "**{typ}** entfernt.", typ=KANAL_TYPEN[typ])
        await interaction.response.send_message(embed=u.ok(txt), ephemeral=True)

    async def ac_ticketart(self, interaction: discord.Interaction, current: str):
        arten = self.bot.cfg.get("tickets", {}).get("arten", [])
        return [app_commands.Choice(name=f"{a.get('emoji', '')} {a['name']}".strip()[:100], value=a.get("kuerzel", a["name"]))
                for a in arten if current.lower() in a["name"].lower()][:25]

    async def ac_einheit(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=n, value=n) for n in self.bot.rechte.einheiten
                if current.lower() in n.lower()][:25]

    @stufe("admin")
    @setup_grp.command(name="kategorie", description="Legt die Discord-Kategorie für Tickets fest (allgemein oder pro Ticket-Art)")
    @app_commands.describe(art="Leer lassen = allgemeine Kategorie für alle Arten ohne eigene Kategorie")
    @app_commands.autocomplete(art=ac_ticketart)
    async def kategorie(self, interaction: discord.Interaction, kategorie: discord.CategoryChannel,
                        art: str | None = None) -> None:
        if art:
            arten = {a.get("kuerzel", a["name"]): a for a in self.bot.cfg.get("tickets", {}).get("arten", [])}
            if art not in arten:
                return await interaction.response.send_message(
                    embed=u.fehler(T("setup.art_unbekannt", "Diese Ticket-Art gibt es nicht.")), ephemeral=True)
            await self.bot.db.set_setting(interaction.guild_id, f"kategorie_ticket_{art}", kategorie.id)
            txt = T("setup.kategorie_art_ok", "**{art}**-Tickets landen in **{kategorie}**.",
                    art=arten[art]["name"], kategorie=kategorie.name)
        else:
            await self.bot.db.set_setting(interaction.guild_id, "kategorie_ticket", kategorie.id)
            txt = T("setup.kategorie_ok", "Tickets landen in **{kategorie}**.", kategorie=kategorie.name)
        await interaction.response.send_message(embed=u.ok(txt), ephemeral=True)

    @stufe("admin")
    @setup_grp.command(name="bewerbungskanal", description="Eigener Bewerbungs-Kanal für eine Einheit")
    @app_commands.describe(kanal="Leer lassen = Einheit nutzt wieder den allgemeinen Bewerbungs-Kanal")
    @app_commands.autocomplete(einheit=ac_einheit)
    async def bewerbungskanal(self, interaction: discord.Interaction, einheit: str,
                              kanal: discord.TextChannel | None = None) -> None:
        e = self.bot.rechte.einheit(einheit)
        if not e:
            return await interaction.response.send_message(
                embed=u.fehler(T("personal.einheit_unbekannt", "Unbekannte Einheit.")), ephemeral=True)
        await self.bot.db.set_setting(interaction.guild_id, f"kanal_bewerbungen_{e.name}", kanal.id if kanal else None)
        txt = T("setup.bewerbungskanal_ok", "Bewerbungen für {emoji} **{einheit}** landen in {kanal}.",
                emoji=e.emoji, einheit=e.name, kanal=kanal.mention) if kanal else \
            T("setup.bewerbungskanal_weg", "{emoji} **{einheit}** nutzt wieder den allgemeinen Bewerbungs-Kanal.",
              emoji=e.emoji, einheit=e.name)
        await interaction.response.send_message(embed=u.ok(txt), ephemeral=True)

    @stufe("admin")
    @setup_grp.command(name="bewerbungskanaele_erstellen",
                       description="Erstellt für jede Einheit einen eigenen Bewerbungs-Kanal (nur für das Karriere Center sichtbar)")
    @app_commands.describe(kategorie="Kategorie, in die die Kanäle kommen (leer = neue Kategorie)")
    async def bewerbungskanaele_erstellen(self, interaction: discord.Interaction,
                                          kategorie: discord.CategoryChannel | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        g = interaction.guild
        ow = {g.default_role: discord.PermissionOverwrite(view_channel=False),
              g.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)}
        for r in self.bot.rechte.rollen_fuer_stufe(g, "karriere"):
            ow[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        if kategorie is None:
            kategorie = await g.create_category(T("setup.bewerbung_kategorie", "📨 Bewerbungen"), overwrites=ow)
        zeilen = []
        einheiten = self.bot.cfg.get("bewerbung", {}).get("einheiten") or list(self.bot.rechte.einheiten)
        for name in einheiten:
            e = self.bot.rechte.einheit(name)
            if not e:
                continue
            vorhanden = await self.bot.db.get_setting(g.id, f"kanal_bewerbungen_{e.name}")
            if vorhanden and (ch := g.get_channel(int(vorhanden))):
                zeilen.append(f"{e.emoji} {e.name} → {ch.mention} ({T('setup.schon_da', 'war schon eingerichtet')})")
                continue
            kanal_name = T("setup.bewerbung_kanalname", "bewerbung-{kurz}", kurz=e.kurz, einheit=e.name).lower().replace(" ", "-")
            try:
                ch = await g.create_text_channel(kanal_name, category=kategorie, overwrites=ow,
                                                 topic=T("setup.bewerbung_topic", "Bewerbungen für {einheit}", einheit=e.name))
            except discord.HTTPException as ex:
                zeilen.append(f"{e.emoji} {e.name} → ❌ {ex}")
                continue
            await self.bot.db.set_setting(g.id, f"kanal_bewerbungen_{e.name}", ch.id)
            zeilen.append(f"{e.emoji} {e.name} → {ch.mention}")
        await interaction.followup.send(embed=u.ok("\n".join(zeilen) or "–",
                                                   T("setup.bewerbungskanaele_titel", "Bewerbungs-Kanäle")), ephemeral=True)

    @stufe("admin")
    @setup_grp.command(name="anzeigen", description="Zeigt die aktuelle Einrichtung")
    async def anzeigen(self, interaction: discord.Interaction) -> None:
        s = await self.bot.db.all_settings(interaction.guild_id)
        zeilen = []
        for k, v in KANAL_TYPEN.items():
            cid = s.get(f"kanal_{k}")
            zeilen.append(f"**{k}** – {f'<#{cid}>' if cid else '❌ nicht gesetzt'}")
        kat = s.get("kategorie_ticket")
        zeilen.append(f"\n**Ticket-Kategorie (allgemein)** – {f'<#{kat}>' if kat else '❌ nicht gesetzt'}")
        for a in self.bot.cfg.get("tickets", {}).get("arten", []):
            k = s.get(f"kategorie_ticket_{a.get('kuerzel', a['name'])}")
            zeilen.append(f"{a.get('emoji', '🎫')} {a['name']} – " + (f"<#{k}>" if k else
                          (f"`{a['kategorie']}` (wird beim 1. Ticket erstellt)" if a.get("kategorie") else "allgemein")))
        zeilen.append("\n**Bewerbungs-Kanäle**")
        for n, e in self.bot.rechte.einheiten.items():
            k = s.get(f"kanal_bewerbungen_{n}")
            zeilen.append(f"{e.emoji} {n} – " + (f"<#{k}>" if k else "allgemein"))
        await interaction.response.send_message(embed=u.embed(T("setup.anzeigen_titel", "⚙️ Einrichtung"), "\n".join(zeilen)), ephemeral=True)

    @stufe("admin")
    @setup_grp.command(name="pruefen", description="Prüft, ob alle Rollen aus der config.yaml auf dem Server existieren")
    async def pruefen(self, interaction: discord.Interaction) -> None:
        g = interaction.guild
        fehlend = sorted(n for n in self.bot.rechte.alle_rollen_namen() if not self.bot.rechte.rolle(g, n))
        me = g.me
        zu_hoch = sorted(n for n in self.bot.rechte.alle_rollen_namen()
                         if (r := self.bot.rechte.rolle(g, n)) and r >= me.top_role)
        e = u.embed(T("setup.check_titel", "🔍 Rollen-Check"))
        e.add_field(name=f"Fehlende Rollen ({len(fehlend)})",
                    value=u.chunk_lines(f"• {n}" for n in fehlend)[0][:1024] if fehlend else "✅ Alle vorhanden",
                    inline=False)
        e.add_field(name=f"Über der Bot-Rolle ({len(zu_hoch)}) – kann ich nicht vergeben",
                    value=u.chunk_lines(f"• {n}" for n in zu_hoch)[0][:1024] if zu_hoch else "✅ Passt",
                    inline=False)
        rechte = me.guild_permissions
        fehlt = [n for n, ok in [("Rollen verwalten", rechte.manage_roles), ("Kanäle verwalten", rechte.manage_channels),
                                 ("Mitglieder timeouten", rechte.moderate_members), ("Kicken", rechte.kick_members),
                                 ("Bannen", rechte.ban_members), ("Nachrichten verwalten", rechte.manage_messages),
                                 ("Nicknames verwalten", rechte.manage_nicknames)] if not ok]
        e.add_field(name="Bot-Berechtigungen", value="✅ Alles da" if not fehlt else "❌ Fehlt: " + ", ".join(fehlt),
                    inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @stufe("admin")
    @setup_grp.command(name="neuladen", description="Lädt die config.yaml neu (Rollen, Einheiten, Dienstgrade …)")
    async def neuladen(self, interaction: discord.Interaction) -> None:
        try:
            self.bot.reload_config()
        except Exception as e:  # noqa: BLE001
            return await interaction.response.send_message(embed=u.fehler(T("setup.config_fehler", "config.yaml fehlerhaft: `{fehler}`", fehler=e)), ephemeral=True)
        await interaction.response.send_message(embed=u.ok(T("setup.config_ok", "Einstellungen neu geladen. (Änderungen an bot.py brauchen einen Neustart.)")), ephemeral=True)


# ==========================================================================
#  MODUL: PERSONAL – Einstellen, Befördern, Uprank/Downrank, Akten, Einheiten
#  /personal – Personalverwaltung  ·  /einheit – Einheiten-Infos  ·  Kontextmenü "Personalakte"
# ==========================================================================

class Personal(commands.Cog):
    personal = app_commands.Group(name="personal", description="Personalverwaltung der Einheiten", guild_only=True)
    einheit_grp = app_commands.Group(name="einheit", description="Infos zu den Einheiten", guild_only=True)

    def __init__(self, bot) -> None:
        self.bot = bot
        self.ctx_akte = app_commands.ContextMenu(name="Personalakte", callback=self._ctx_akte)
        self.ctx_akte.guild_only = True
        self.ctx_akte.extras["perm"] = "jeder"
        bot.tree.add_command(self.ctx_akte)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_akte.name, type=self.ctx_akte.type)

    @property
    def r(self):
        return self.bot.rechte

    # ================================================================ Helfer
    async def soldat(self, guild_id: int, user_id: int):
        return await self.bot.db.fetchone(
            "SELECT * FROM soldaten WHERE guild_id=? AND user_id=? AND status='aktiv'", guild_id, user_id)

    async def log(self, guild: discord.Guild, user: discord.abc.User, aktion: str, details: str,
                  von: discord.abc.User, farbe: discord.Color | None = None) -> None:
        await self.bot.db.execute(
            "INSERT INTO personal_log (guild_id,user_id,aktion,details,von,zeit) VALUES (?,?,?,?,?,?)",
            guild.id, user.id, aktion, details, von.id, u.now())
        e = u.embed(T("personal.log_titel", "📁 {aktion}", aktion=aktion), f"{user.mention} (`{user}`)\n{details}", farbe)
        e.add_field(name=T("personal.log_durch", "Durch"), value=von.mention)
        await u.send_log(self.bot, guild, "personal", e)

    async def bekanntgabe(self, guild: discord.Guild, e: discord.Embed, user: discord.Member | None = None) -> None:
        cid = await self.bot.db.get_setting(guild.id, "kanal_befoerderungen")
        if cid and (ch := guild.get_channel(int(cid))):
            try:
                await ch.send(content=P("befoerderung", guild, user), embed=e,
                              allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True))
            except discord.HTTPException:
                pass

    async def setze_rollen(self, member: discord.Member, einheit: Einheit, pos: int,
                           alte: Einheit | None = None) -> list[str]:
        """Vergibt die passenden Rollen. Gibt die Namen fehlender Rollen zurück."""
        g = member.guild
        fehlend: list[str] = []
        weg: set[discord.Role] = set()
        for e in {einheit.name: einheit, **({alte.name: alte} if alte else {})}.values():
            for p in e.positionen:
                if (rolle := self.r.rolle(g, p.rolle)):
                    weg.add(rolle)
        neu_namen = [einheit.positionen[pos].rolle]
        bp = self.r.basis_position
        if pos >= bp and bp < len(einheit.positionen):
            neu_namen.append(einheit.positionen[bp].rolle)
        neu_namen += self.r.zusatzrollen
        neu: set[discord.Role] = set()
        for n in neu_namen:
            if (rolle := self.r.rolle(g, n)):
                neu.add(rolle)
            else:
                fehlend.append(n)
        entfernen = [x for x in weg if x not in neu and x in member.roles]
        geben = [x for x in neu if x not in member.roles]
        if entfernen:
            await member.remove_roles(*entfernen, reason="BwRP Personalverwaltung")
        if geben:
            await member.add_roles(*geben, reason="BwRP Personalverwaltung")
        return fehlend

    async def update_nick(self, member: discord.Member) -> None:
        conf = self.bot.cfg.get("personal", {}).get("nickname", {})
        if not conf.get("aktiv"):
            return
        row = await self.soldat(member.guild.id, member.id)
        if not row:
            return
        e = self.r.einheit(row["einheit"])
        dg = self.r.dienstgrade[row["dienstgrad"]] if row["dienstgrad"] < len(self.r.dienstgrade) else None
        nick = conf.get("format", "{einheit_kurz} | {dienstgrad_kurz} {name}").format(
            einheit=e.name if e else "", einheit_kurz=e.kurz if e else "",
            dienstgrad=dg.name if dg else "", dienstgrad_kurz=dg.kurz if dg else "",
            name=row["rp_name"] or member.name)
        try:
            await member.edit(nick=nick[:32], reason="BwRP Nickname")
        except discord.HTTPException:
            pass

    def darf(self, actor: discord.Member, einheit: Einheit, ziel_pos: int | None = None,
             ziel: discord.Member | None = None) -> str | None:
        maxp = self.r.verwaltung(actor, einheit)
        if maxp < 0:
            return T("personal.darf_einheit_nicht", "Du darfst die Einheit **{einheit}** nicht verwalten.", einheit=einheit.name)
        if ziel_pos is not None and ziel_pos >= maxp:
            return T("personal.nur_unterhalb", "Du kannst nur Positionen **unterhalb** deiner eigenen vergeben.")
        if ziel is not None and not self.r.ist_global(actor):
            if ziel.id == actor.id:
                return T("personal.nicht_selbst", "Du kannst dich nicht selbst bearbeiten.")
            if self.r.position_von(ziel, einheit) >= maxp:
                return T("personal.zu_hoch", "Diese Person steht gleich hoch oder höher als du.")
        return None

    async def einstellen_intern(self, member: discord.Member, einheit: Einheit, pos: int,
                                von: discord.abc.User, rp_name: str | None = None) -> list[str]:
        alt = await self.soldat(member.guild.id, member.id)
        alte = self.r.einheit(alt["einheit"]) if alt else None
        fehlend = await self.setze_rollen(member, einheit, pos, alte if alte and alte.name != einheit.name else None)
        await self.bot.db.execute(
            "INSERT INTO soldaten (guild_id,user_id,einheit,position,dienstgrad,rp_name,eintritt,status) "
            "VALUES (?,?,?,?,?,?,?, 'aktiv') ON CONFLICT(guild_id,user_id) DO UPDATE SET einheit=excluded.einheit, "
            "position=excluded.position, status='aktiv', rp_name=COALESCE(excluded.rp_name, soldaten.rp_name), "
            "eintritt=CASE WHEN soldaten.status='aktiv' THEN soldaten.eintritt ELSE excluded.eintritt END",
            member.guild.id, member.id, einheit.name, pos, alt["dienstgrad"] if alt else 0, rp_name, u.now())
        await self.update_nick(member)
        return fehlend

    def _fehlend_hinweis(self, fehlend: list[str]) -> str:
        return ("\n\n" + T("personal.rollen_fehlen", "⚠️ Diese Rollen gibt es nicht auf dem Server: {rollen}",
                              rollen=", ".join(f"`{f}`" for f in fehlend))) if fehlend else ""

    async def _antwort(self, interaction: discord.Interaction, e: discord.Embed) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(embed=e, ephemeral=True)
        else:
            await interaction.response.send_message(embed=e, ephemeral=True)

    # ============================================================ /personal
    @stufe("personal")
    @personal.command(name="einstellen", description="Stellt jemanden in eine Einheit ein")
    @app_commands.describe(user="Wer", einheit="Welche Einheit", position="Position (Standard: niedrigste)",
                           rp_name="Name im Roleplay")
    @app_commands.autocomplete(einheit=ac.einheit, position=ac.position)
    async def einstellen(self, interaction: discord.Interaction, user: discord.Member, einheit: str,
                         position: int = 0, rp_name: str | None = None) -> None:
        e = self.r.einheit(einheit)
        if not e:
            return await self._antwort(interaction, u.fehler(T("personal.einheit_unbekannt", "Unbekannte Einheit.")))
        if not 0 <= position < len(e.positionen):
            return await self._antwort(interaction, u.fehler(T("personal.position_ungueltig", "Ungültige Position.")))
        if (f := self.darf(interaction.user, e, position, user)):
            return await self._antwort(interaction, u.fehler(f))
        vorher = await self.soldat(interaction.guild_id, user.id)
        if vorher and vorher["einheit"] != e.name:
            return await self._antwort(interaction, u.fehler(T(
                "personal.schon_in_einheit", "{user} ist schon bei **{einheit}**. Nutze `/personal versetzen`.",
                user=user.mention, einheit=vorher['einheit'])))
        await interaction.response.defer(ephemeral=True)
        fehlend = await self.einstellen_intern(user, e, position, interaction.user, rp_name)
        titel = e.positionen[position].titel
        await self.log(interaction.guild, user, T("personal.aktion_einstellung", "Einstellung"),
                       T("personal.einstellung_log", "{emoji} **{einheit}** als **{position}**", emoji=e.emoji, einheit=e.name, position=titel),
                       interaction.user, u.GRUEN)
        await u.dm(user, u.embed(T("personal.einstellung_dm_titel", "{emoji} Willkommen in der Einheit {einheit}", emoji=e.emoji, einheit=e.name),
                                 T("personal.einstellung_dm", "Du wurdest auf **{server}** als **{position}** eingestellt.",
                                   server=interaction.guild.name, position=titel)))
        await self._antwort(interaction, u.ok(T("personal.einstellung_ok", "{user} ist jetzt **{position}** bei **{einheit}**.", user=user.mention, position=titel, einheit=e.name)
                                              + self._fehlend_hinweis(fehlend)))

    @stufe("personal")
    @personal.command(name="position", description="Ändert die Position innerhalb der Einheit")
    @app_commands.autocomplete(position=ac.position)
    async def position(self, interaction: discord.Interaction, user: discord.Member, position: int,
                       grund: str | None = None) -> None:
        row = await self.soldat(interaction.guild_id, user.id)
        e = self.r.einheit(row["einheit"]) if row else None
        if not e:
            return await self._antwort(interaction, u.fehler(T("personal.nicht_eingetragen", "Diese Person ist in keiner Einheit eingetragen.")))
        if not 0 <= position < len(e.positionen):
            return await self._antwort(interaction, u.fehler(T("personal.position_ungueltig", "Ungültige Position.")))
        if (f := self.darf(interaction.user, e, position, user)):
            return await self._antwort(interaction, u.fehler(f))
        await interaction.response.defer(ephemeral=True)
        alt = e.positionen[row["position"]].titel if row["position"] < len(e.positionen) else "?"
        fehlend = await self.setze_rollen(user, e, position)
        await self.bot.db.execute("UPDATE soldaten SET position=? WHERE guild_id=? AND user_id=?",
                                  position, interaction.guild_id, user.id)
        neu = e.positionen[position].titel
        hoch = position > row["position"]
        await self.log(interaction.guild, user, T("personal.aktion_position", "Positionswechsel"), f"**{e.name}**: {alt} → **{neu}**"
                       + ("\n" + T("personal.grund", "Grund: {grund}", grund=grund) if grund else ""), interaction.user, u.GRUEN if hoch else u.GELB)
        if hoch:
            await self.bekanntgabe(interaction.guild, u.embed(
                T("personal.position_bekanntgabe_titel", "🎖️ Neue Position"),
                T("personal.position_bekanntgabe", "{user} wurde von {von} zum **{position}** bei {emoji} **{einheit}** aufgestuft. Herzlichen Glückwunsch!",
                  user=user.mention, von=interaction.user.mention, position=neu, emoji=e.emoji, einheit=e.name)), user)
        await self._antwort(interaction, u.ok(f"{user.mention}: {alt} → **{neu}**" + self._fehlend_hinweis(fehlend)))

    @stufe("personal")
    @app_commands.command(name="uprank", description="Gibt jemandem einen Uprank (Rolle) und kündigt ihn im Beförderungs-Kanal an")
    @app_commands.guild_only()
    @app_commands.describe(user="Wer wird aufgestuft?", rolle="Zu welcher Rolle? z. B. Wachbataillon",
                           grund="Grund (optional)")
    async def uprank(self, interaction: discord.Interaction, user: discord.Member, rolle: discord.Role,
                     grund: str | None = None) -> None:
        g = interaction.guild
        if rolle.is_default() or rolle.managed:
            return await self._antwort(interaction, u.fehler(T("personal.uprank_rolle_ungueltig", "Diese Rolle kann nicht vergeben werden.")))
        if rolle >= g.me.top_role:
            return await self._antwort(interaction, u.fehler(T("personal.uprank_bot_zu_niedrig", "Die Bot-Rolle muss über {rolle} stehen.", rolle=rolle.mention)))
        if not self.r.ist_global(interaction.user) and rolle >= interaction.user.top_role:
            return await self._antwort(interaction, u.fehler(T("personal.uprank_zu_hoch", "Du kannst nur Rollen vergeben, die unter deiner höchsten Rolle stehen.")))
        if rolle in user.roles:
            return await self._antwort(interaction, u.warnung(T("personal.uprank_schon", "{user} hat {rolle} bereits.", user=user.mention, rolle=rolle.mention)))
        await interaction.response.defer(ephemeral=True)
        try:
            await user.add_roles(rolle, reason=f"Uprank durch {interaction.user}")
        except discord.HTTPException:
            return await self._antwort(interaction, u.fehler(T("personal.uprank_fehler", "Konnte die Rolle nicht vergeben.")))
        await self.log(g, user, T("personal.aktion_uprank", "Uprank"), f"→ **{rolle.name}**"
                       + ("\n" + T("personal.grund", "Grund: {grund}", grund=grund) if grund else ""), interaction.user, u.GRUEN)
        await self.bekanntgabe(g, u.embed(
            T("personal.uprank_titel", "🎖️ Uprank"),
            T("personal.uprank_text", "{user} wurde von {von} zu {rolle} aufgestuft. Herzlichen Glückwunsch!",
              user=user.mention, von=interaction.user.mention, rolle=rolle.mention) + (f"\n> {grund}" if grund else "")), user)
        await u.dm(user, u.embed(T("personal.uprank_dm_titel", "🎖️ Uprank"),
                                 T("personal.uprank_dm", "Du wurdest von {von} zu **{rolle}** aufgestuft.", von=interaction.user.display_name, rolle=rolle.name)))
        await self._antwort(interaction, u.ok(T("personal.uprank_ok", "{user} wurde zu {rolle} aufgestuft.", user=user.mention, rolle=rolle.mention)))

    @stufe("personal")
    @app_commands.command(name="downrank", description="Nimmt jemandem eine Rolle ab (Downrank) und kündigt es im Beförderungs-Kanal an")
    @app_commands.guild_only()
    @app_commands.describe(user="Wer wird abgestuft?", rolle="Welche Rolle wird entfernt? z. B. Wachbataillon",
                           grund="Grund (optional)")
    async def downrank(self, interaction: discord.Interaction, user: discord.Member, rolle: discord.Role,
                       grund: str | None = None) -> None:
        g = interaction.guild
        if rolle.is_default() or rolle.managed:
            return await self._antwort(interaction, u.fehler(T("personal.downrank_rolle_ungueltig", "Diese Rolle kann nicht entfernt werden.")))
        if rolle >= g.me.top_role:
            return await self._antwort(interaction, u.fehler(T("personal.uprank_bot_zu_niedrig", "Die Bot-Rolle muss über {rolle} stehen.", rolle=rolle.mention)))
        if not self.r.ist_global(interaction.user) and rolle >= interaction.user.top_role:
            return await self._antwort(interaction, u.fehler(T("personal.downrank_zu_hoch", "Du kannst nur Rollen entfernen, die unter deiner höchsten Rolle stehen.")))
        if rolle not in user.roles:
            return await self._antwort(interaction, u.warnung(T("personal.downrank_hat_nicht", "{user} hat {rolle} gar nicht.", user=user.mention, rolle=rolle.mention)))
        await interaction.response.defer(ephemeral=True)
        try:
            await user.remove_roles(rolle, reason=f"Downrank durch {interaction.user}")
        except discord.HTTPException:
            return await self._antwort(interaction, u.fehler(T("personal.downrank_fehler", "Konnte die Rolle nicht entfernen.")))
        await self.log(g, user, T("personal.aktion_downrank", "Downrank"), f"✖ **{rolle.name}**"
                       + ("\n" + T("personal.grund", "Grund: {grund}", grund=grund) if grund else ""), interaction.user, u.ROT)
        await self.bekanntgabe(g, u.embed(
            T("personal.downrank_titel", "📉 Downrank"),
            T("personal.downrank_text", "{user} wurde von {von} aus {rolle} abgestuft.",
              user=user.mention, von=interaction.user.mention, rolle=rolle.mention) + (f"\n> {grund}" if grund else ""), u.ROT), user)
        await u.dm(user, u.embed(T("personal.downrank_dm_titel", "📉 Downrank"),
                                 T("personal.downrank_dm", "Du wurdest von {von} aus **{rolle}** abgestuft.", von=interaction.user.display_name, rolle=rolle.name)
                                 + (f"\n> {grund}" if grund else ""), u.ROT))
        await self._antwort(interaction, u.ok(T("personal.downrank_ok", "{user} wurde aus {rolle} abgestuft.", user=user.mention, rolle=rolle.mention)))

    async def _dienstgrad_setzen(self, interaction: discord.Interaction, user: discord.Member, neu: int,
                                 grund: str | None, aktion: str) -> None:
        row = await self.soldat(interaction.guild_id, user.id)
        e = self.r.einheit(row["einheit"]) if row else None
        if not e:
            return await self._antwort(interaction, u.fehler(T("personal.nicht_eingetragen", "Diese Person ist in keiner Einheit eingetragen.")))
        if (f := self.darf(interaction.user, e, None, user)):
            return await self._antwort(interaction, u.fehler(f))
        dgs = self.r.dienstgrade
        if not dgs:
            return await self._antwort(interaction, u.fehler(T("personal.keine_dienstgrade", "In der config.yaml sind keine Dienstgrade definiert.")))
        if not 0 <= neu < len(dgs):
            return await self._antwort(interaction, u.fehler(T("personal.kein_dienstgrad", "Es gibt keinen höheren/niedrigeren Dienstgrad.")))
        # Nicht-globale Personaler dürfen maximal bis zum eigenen Dienstgrad – 1 befördern
        if not self.r.ist_global(interaction.user):
            eigen = await self.soldat(interaction.guild_id, interaction.user.id)
            if eigen and neu >= eigen["dienstgrad"]:
                return await self._antwort(interaction, u.fehler(T("personal.nur_unter_eigenem", "Du kannst nur bis unter deinen eigenen Dienstgrad befördern.")))
        alt = row["dienstgrad"]
        await self.bot.db.execute("UPDATE soldaten SET dienstgrad=? WHERE guild_id=? AND user_id=?",
                                  neu, interaction.guild_id, user.id)
        await self.update_nick(user)
        alt_name = dgs[alt].name if alt < len(dgs) else "?"
        hoch = neu > alt
        await self.log(interaction.guild, user, aktion, f"{alt_name} → **{dgs[neu].name}**"
                       + ("\n" + T("personal.grund", "Grund: {grund}", grund=grund) if grund else ""), interaction.user, u.GRUEN if hoch else u.ROT)
        if hoch:
            await self.bekanntgabe(interaction.guild, u.embed(
                T("personal.befoerderung_titel", "🎖️ Beförderung"),
                T("personal.befoerderung_text", "{user} wurde von {von} zum **{dienstgrad}** befördert. Herzlichen Glückwunsch!",
                  user=user.mention, von=interaction.user.mention, dienstgrad=dgs[neu].name) + (f"\n> {grund}" if grund else "")), user)
        await u.dm(user, u.embed(T("personal.dienstgrad_dm_titel", "🎖️ {aktion}", aktion=aktion),
                                 T("personal.dienstgrad_dm", "Dein Dienstgrad: {alt} → **{neu}**", alt=alt_name, neu=dgs[neu].name)
                                 + ("\n" + T("personal.grund", "Grund: {grund}", grund=grund) if grund else "")))
        await self._antwort(interaction, u.ok(f"{user.mention}: {alt_name} → **{dgs[neu].name}**"))

    @stufe("personal")
    @personal.command(name="befoerdern", description="Befördert jemanden um einen Dienstgrad")
    async def befoerdern(self, interaction: discord.Interaction, user: discord.Member, grund: str | None = None) -> None:
        row = await self.soldat(interaction.guild_id, user.id)
        await self._dienstgrad_setzen(interaction, user, (row["dienstgrad"] + 1) if row else 0, grund, T("personal.aktion_befoerderung", "Beförderung"))

    @stufe("personal")
    @personal.command(name="degradieren", description="Degradiert jemanden um einen Dienstgrad")
    async def degradieren(self, interaction: discord.Interaction, user: discord.Member, grund: str) -> None:
        row = await self.soldat(interaction.guild_id, user.id)
        await self._dienstgrad_setzen(interaction, user, (row["dienstgrad"] - 1) if row else -1, grund, T("personal.aktion_degradierung", "Degradierung"))

    @stufe("personal")
    @personal.command(name="dienstgrad", description="Setzt einen bestimmten Dienstgrad")
    @app_commands.autocomplete(dienstgrad=ac.dienstgrad)
    async def dienstgrad(self, interaction: discord.Interaction, user: discord.Member, dienstgrad: int,
                         grund: str | None = None) -> None:
        await self._dienstgrad_setzen(interaction, user, dienstgrad, grund, T("personal.aktion_dienstgrad", "Dienstgrad geändert"))

    @stufe("personal")
    @personal.command(name="versetzen", description="Versetzt jemanden in eine andere Einheit")
    @app_commands.autocomplete(einheit=ac.einheit, position=ac.position)
    async def versetzen(self, interaction: discord.Interaction, user: discord.Member, einheit: str,
                        position: int = 0, grund: str | None = None) -> None:
        row = await self.soldat(interaction.guild_id, user.id)
        alt = self.r.einheit(row["einheit"]) if row else None
        neu = self.r.einheit(einheit)
        if not neu or not 0 <= position < len(neu.positionen):
            return await self._antwort(interaction, u.fehler(T("personal.einheit_position_unbekannt", "Unbekannte Einheit oder Position.")))
        if alt and (f := self.darf(interaction.user, alt, None, user)):
            return await self._antwort(interaction, u.fehler(T("personal.alte_einheit", "Alte Einheit: {fehler}", fehler=f)))
        if (f := self.darf(interaction.user, neu, position)):
            return await self._antwort(interaction, u.fehler(T("personal.neue_einheit", "Neue Einheit: {fehler}", fehler=f)))
        await interaction.response.defer(ephemeral=True)
        fehlend = await self.einstellen_intern(user, neu, position, interaction.user)
        await self.log(interaction.guild, user, T("personal.aktion_versetzung", "Versetzung"),
                       f"{alt.name if alt else '–'} → **{neu.name}** ({neu.positionen[position].titel})"
                       + ("\n" + T("personal.grund", "Grund: {grund}", grund=grund) if grund else ""), interaction.user)
        await self._antwort(interaction, u.ok(T("personal.versetzt_ok", "{user} wurde zu **{einheit}** versetzt.", user=user.mention, einheit=neu.name)
                                              + self._fehlend_hinweis(fehlend)))

    @stufe("personal")
    @personal.command(name="entlassen", description="Entlässt jemanden aus seiner Einheit")
    async def entlassen(self, interaction: discord.Interaction, user: discord.Member, grund: str) -> None:
        row = await self.soldat(interaction.guild_id, user.id)
        e = self.r.einheit(row["einheit"]) if row else None
        if not e:
            return await self._antwort(interaction, u.fehler(T("personal.nicht_eingetragen", "Diese Person ist in keiner Einheit eingetragen.")))
        if (f := self.darf(interaction.user, e, None, user)):
            return await self._antwort(interaction, u.fehler(f))
        await interaction.response.defer(ephemeral=True)
        weg = [r for p in e.positionen if (r := self.r.rolle(interaction.guild, p.rolle)) and r in user.roles]
        weg += [r for n in self.r.zusatzrollen if (r := self.r.rolle(interaction.guild, n)) and r in user.roles]
        if weg:
            await user.remove_roles(*weg, reason=f"Entlassung: {grund}")
        await self.bot.db.execute("UPDATE soldaten SET status='entlassen' WHERE guild_id=? AND user_id=?",
                                  interaction.guild_id, user.id)
        await self.log(interaction.guild, user, T("personal.aktion_entlassung", "Entlassung"),
                       T("personal.entlassung_log", "aus **{einheit}**\nGrund: {grund}", einheit=e.name, grund=grund), interaction.user, u.ROT)
        await u.dm(user, u.embed(T("personal.entlassung_dm_titel", "📄 Entlassung"), T("personal.entlassung_dm", "Du wurdest aus **{einheit}** entlassen.\nGrund: {grund}", einheit=e.name, grund=grund), u.ROT))
        await self._antwort(interaction, u.ok(T("personal.entlassen_ok", "{user} wurde aus **{einheit}** entlassen.", user=user.mention, einheit=e.name)))

    @stufe("personal")
    @personal.command(name="rpname", description="Setzt den Roleplay-Namen einer Person")
    async def rpname(self, interaction: discord.Interaction, user: discord.Member,
                     name: app_commands.Range[str, 1, 32]) -> None:
        row = await self.soldat(interaction.guild_id, user.id)
        if not row:
            return await self._antwort(interaction, u.fehler(T("personal.nicht_eingetragen", "Diese Person ist in keiner Einheit eingetragen.")))
        await self.bot.db.execute("UPDATE soldaten SET rp_name=? WHERE guild_id=? AND user_id=?",
                                  name, interaction.guild_id, user.id)
        await self.update_nick(user)
        await self._antwort(interaction, u.ok(T("personal.rpname_ok", "RP-Name von {user}: **{name}**", user=user.mention, name=name)))

    @stufe("personal")
    @personal.command(name="notiz", description="Fügt der Personalakte eine interne Notiz hinzu")
    async def notiz(self, interaction: discord.Interaction, user: discord.Member,
                    text: app_commands.Range[str, 1, 500]) -> None:
        await self.bot.db.execute("INSERT INTO notizen (guild_id,user_id,text,von,zeit) VALUES (?,?,?,?,?)",
                                  interaction.guild_id, user.id, text, interaction.user.id, u.now())
        await self._antwort(interaction, u.ok(T("personal.notiz_ok", "Notiz zu {user} gespeichert.", user=user.mention)))

    @stufe("personal")
    @personal.command(name="verlauf", description="Zeigt den kompletten Personal-Verlauf einer Person")
    async def verlauf(self, interaction: discord.Interaction, user: discord.Member) -> None:
        rows = await self.bot.db.fetchall(
            "SELECT * FROM personal_log WHERE guild_id=? AND user_id=? ORDER BY zeit DESC LIMIT 40",
            interaction.guild_id, user.id)
        zeilen = [f"{u.ts(r['zeit'], 'd')} · **{r['aktion']}** – {r['details'].splitlines()[0]} (<@{r['von']}>)"
                  for r in rows] or [T("personal.kein_verlauf", "Kein Verlauf.")]
        await self._antwort(interaction, u.embed(T("personal.verlauf_titel", "📜 Verlauf – {name}", name=user.display_name), u.chunk_lines(zeilen)[0]))

    @stufe("jeder")
    @personal.command(name="akte", description="Zeigt die Personalakte (eigene oder – mit Rechten – von anderen)")
    async def akte(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        await self._akte(interaction, user or interaction.user)

    async def _ctx_akte(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self._akte(interaction, user)

    async def _akte(self, interaction: discord.Interaction, user: discord.Member) -> None:
        viewer = interaction.user
        intern = self.r.hat_stufe(viewer, "personal") or self.r.hat_stufe(viewer, "moderator")
        if user.id != viewer.id and not intern:
            return await self._antwort(interaction, u.fehler(T("personal.nur_eigene_akte", "Du darfst nur deine eigene Akte ansehen.")))
        db, gid = self.bot.db, interaction.guild_id
        row = await self.soldat(gid, user.id)
        e = u.embed(T("personal.akte_titel", "🗂️ Personalakte – {name}", name=user.display_name))
        e.set_thumbnail(url=user.display_avatar.url)
        if row:
            ein = self.r.einheit(row["einheit"])
            dgs = self.r.dienstgrade
            e.add_field(name=T("personal.feld_einheit", "Einheit"), value=f"{ein.emoji} {ein.name}" if ein else row["einheit"])
            e.add_field(name=T("personal.feld_position", "Position"), value=ein.positionen[row["position"]].titel
                        if ein and row["position"] < len(ein.positionen) else "–")
            e.add_field(name=T("personal.feld_dienstgrad", "Dienstgrad"), value=dgs[row["dienstgrad"]].name if row["dienstgrad"] < len(dgs) else "–")
            e.add_field(name=T("personal.feld_rpname", "RP-Name"), value=row["rp_name"] or "–")
            e.add_field(name=T("personal.feld_eintritt", "Eintritt"), value=u.ts(row["eintritt"], "D"))
        else:
            e.description = T("personal.akte_keine_einheit", "Aktuell in keiner Einheit eingetragen.")
        dienst = await db.fetchone("SELECT COALESCE(SUM(COALESCE(ende, strftime('%s','now')) - start),0) s "
                                   "FROM dienst WHERE guild_id=? AND user_id=?", gid, user.id)
        e.add_field(name=T("personal.feld_dienstzeit", "Dienstzeit gesamt"), value=u.fmt_dauer(dienst["s"] or 0))
        lehr = await db.fetchall("SELECT lehrgang FROM lehrgaenge WHERE guild_id=? AND user_id=?", gid, user.id)
        e.add_field(name=T("personal.feld_lehrgaenge", "Lehrgänge ({anzahl})", anzahl=len(lehr)), value=", ".join(r["lehrgang"] for r in lehr) or "–", inline=False)
        warns = await db.fetchone("SELECT COUNT(*) c FROM warns WHERE guild_id=? AND user_id=?", gid, user.id)
        e.add_field(name=T("personal.feld_warns", "Verwarnungen"), value=str(warns["c"]))
        if intern:
            notes = await db.fetchall("SELECT * FROM notizen WHERE guild_id=? AND user_id=? ORDER BY zeit DESC LIMIT 5",
                                      gid, user.id)
            if notes:
                e.add_field(name=T("personal.feld_notizen", "🔒 Interne Notizen"), inline=False, value="\n".join(
                    f"{u.ts(n['zeit'], 'd')} <@{n['von']}>: {n['text'][:150]}" for n in notes)[:1024])
        await self._antwort(interaction, e)

    # ============================================================== /einheit
    @stufe("jeder")
    @einheit_grp.command(name="uebersicht", description="Alle Einheiten mit Mitgliederzahl")
    async def uebersicht(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.fetchall("SELECT einheit, COUNT(*) c FROM soldaten WHERE guild_id=? AND status='aktiv' "
                                          "GROUP BY einheit", interaction.guild_id)
        anzahl = {r["einheit"]: r["c"] for r in rows}
        zeilen = [T("einheit.zeile", "{emoji} **{name}** ({kurz}) – {anzahl} Soldaten", emoji=e.emoji, name=e.name, kurz=e.kurz, anzahl=anzahl.get(e.name, 0))
                  for e in self.r.einheiten.values()]
        zeilen.append("\n" + T("einheit.gesamt", "**Gesamt:** {anzahl} aktive Soldaten", anzahl=sum(anzahl.values())))
        await interaction.response.send_message(embed=u.embed(T("einheit.titel", "🪖 Einheiten"), "\n".join(zeilen)))

    @stufe("jeder")
    @einheit_grp.command(name="mitglieder", description="Zeigt alle Mitglieder einer Einheit nach Position")
    @app_commands.autocomplete(einheit=ac.einheit)
    async def mitglieder(self, interaction: discord.Interaction, einheit: str) -> None:
        e = self.r.einheit(einheit)
        if not e:
            return await self._antwort(interaction, u.fehler(T("personal.einheit_unbekannt", "Unbekannte Einheit.")))
        rows = await self.bot.db.fetchall(
            "SELECT * FROM soldaten WHERE guild_id=? AND einheit=? AND status='aktiv' ORDER BY position DESC, dienstgrad DESC",
            interaction.guild_id, e.name)
        dgs = self.r.dienstgrade
        zeilen, akt = [], None
        for r in rows:
            if r["position"] != akt:
                akt = r["position"]
                zeilen.append(f"\n**{e.positionen[akt].titel if akt < len(e.positionen) else '?'}**")
            dg = dgs[r["dienstgrad"]].kurz if r["dienstgrad"] < len(dgs) else ""
            zeilen.append(f"• {dg} <@{r['user_id']}>" + (f" ({r['rp_name']})" if r["rp_name"] else ""))
        await interaction.response.send_message(
            embed=u.embed(T("einheit.mitglieder_titel", "{emoji} {name} – {anzahl} Mitglieder", emoji=e.emoji, name=e.name, anzahl=len(rows)), u.chunk_lines(zeilen or [T("einheit.keine_mitglieder", "Keine Mitglieder.")])[0]))

    @stufe("jeder")
    @einheit_grp.command(name="info", description="Zeigt die Positionen/Rollen einer Einheit")
    @app_commands.autocomplete(einheit=ac.einheit)
    async def info(self, interaction: discord.Interaction, einheit: str) -> None:
        e = self.r.einheit(einheit)
        if not e:
            return await self._antwort(interaction, u.fehler(T("personal.einheit_unbekannt", "Unbekannte Einheit.")))
        zeilen = []
        for i, p in reversed(list(enumerate(e.positionen))):
            rolle = self.r.rolle(interaction.guild, p.rolle)
            zeilen.append(f"`{i}` **{p.titel}** – {rolle.mention if rolle else f'❌ `{p.rolle}`'}")
        await interaction.response.send_message(embed=u.embed(f"{e.emoji} {e.name} ({e.kurz})", "\n".join(zeilen)),
                                                ephemeral=True)

    @stufe("jeder")
    @einheit_grp.command(name="dienstgrade", description="Zeigt alle Dienstgrade")
    async def dienstgrade(self, interaction: discord.Interaction) -> None:
        zeilen, gruppe = [], None
        for i, d in enumerate(self.r.dienstgrade):
            if d.gruppe and d.gruppe != gruppe:
                gruppe = d.gruppe
                zeilen.append(f"\n**{gruppe}**")
            zeilen.append(f"`{i:>2}` {d.name} ({d.kurz})")
        await interaction.response.send_message(embed=u.embed(T("einheit.dienstgrade_titel", "🎖️ Dienstgrade"), "\n".join(zeilen) or "–"), ephemeral=True)


# ==========================================================================
#  MODUL: KARRIERE – Bewerbungen, Ausbildung/Lehrgänge, Ausbildungs-Ankündigung
#  Karriere Center: Bewerbungen per Button/Formular  ·  /ausbildung – Lehrgänge
# ==========================================================================

# ---------------------------------------------------------------- Hilfen
async def bewerbungs_kanal(bot, guild: discord.Guild, einheit: str) -> discord.TextChannel | None:
    """Eigener Kanal der Einheit (/setup bewerbungskanal) – sonst der allgemeine Bewerbungs-Kanal."""
    for key in (f"kanal_bewerbungen_{einheit}", "kanal_bewerbungen"):
        cid = await bot.db.get_setting(guild.id, key)
        if cid and (ch := guild.get_channel(int(cid))):
            return ch
    return None


async def darf_bewerben(bot, guild_id: int, user_id: int) -> str | None:
    """Gibt einen Hinweistext zurück, wenn sich die Person gerade nicht bewerben darf."""
    offen = await bot.db.fetchone("SELECT id FROM bewerbungen WHERE guild_id=? AND user_id=? AND status='offen'",
                                  guild_id, user_id)
    if offen:
        return T("karriere.schon_offen", "Du hast schon eine offene Bewerbung (#{nummer}).", nummer=offen["id"])
    tage = bot.cfg.get("bewerbung", {}).get("sperre_nach_ablehnung_tage", 0)
    if tage:
        abgelehnt = await bot.db.fetchone(
            "SELECT zeit FROM bewerbungen WHERE guild_id=? AND user_id=? AND status='abgelehnt' ORDER BY zeit DESC",
            guild_id, user_id)
        if abgelehnt and abgelehnt["zeit"] + tage * 86400 > u.now():
            return T("karriere.gesperrt", "Du kannst dich erst wieder {zeit} bewerben.",
                     zeit=u.ts(abgelehnt["zeit"] + tage * 86400, "R"))
    return None


def einheiten_liste(bot) -> list[str]:
    return bot.cfg.get("bewerbung", {}).get("einheiten") or list(bot.rechte.einheiten)


# ---------------------------------------------------------------- Formular
def fragen_seiten(bot) -> list[list[dict]]:
    """Fragen in Formular-Teile à 5 Stück aufteilen (Discord erlaubt pro Formular max. 5 Felder)."""
    f = list(bot.cfg.get("bewerbung", {}).get("fragen", []))
    return [f[i:i + 5] for i in range(0, len(f), 5)] or [[]]


def einheit_frage_text(bot) -> str:
    return bot.cfg.get("bewerbung", {}).get("einheit_frage") or T("karriere.einheit_frage", "Für welche Division bewirbst du dich?")


class WeiterView(discord.ui.View):
    """Zwischen zwei Formular-Teilen: zeigt die nächsten Fragen und einen Weiter-Knopf."""

    def __init__(self, bot, guild_id: int, einheit: str, antworten: list[dict], teil: int, user_id: int) -> None:
        super().__init__(timeout=1800)
        self.bot, self.guild_id, self.einheit = bot, guild_id, einheit
        self.antworten, self.teil, self.user_id = antworten, teil, user_id
        self.weiter.label = T("karriere.knopf_weiter", "Weiter zu Teil {teil}/{gesamt}", teil=teil + 1, gesamt=len(fragen_seiten(bot)))

    @discord.ui.button(label="Weiter", emoji="➡️", style=discord.ButtonStyle.success)
    async def weiter(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(embed=u.fehler(T("karriere.nicht_deins", "Das ist nicht deine Bewerbung.")), ephemeral=True)
        await interaction.response.send_modal(BewerbungModal(self.bot, self.guild_id, self.einheit, self.teil, self.antworten))

    async def on_timeout(self) -> None:
        self.stop()


class BewerbungModal(discord.ui.Modal):
    def __init__(self, bot, guild_id: int, einheit: str, teil: int = 0, bisher: list[dict] | None = None) -> None:
        seiten = fragen_seiten(bot)
        super().__init__(title=T("karriere.modal_titel", "{einheit} – Teil {teil}/{gesamt}",
                                 einheit=einheit, teil=teil + 1, gesamt=len(seiten))[:45])
        self.bot = bot
        self.guild_id = guild_id
        self.einheit = einheit
        self.teil = teil
        self.bisher = list(bisher or [])
        self.felder: list[discord.ui.TextInput] = []
        self.fragen: list[str] = []
        for f in seiten[teil]:
            ti = discord.ui.TextInput(
                label=(f.get("kurz") or f["frage"])[:45], placeholder=(f.get("platzhalter") or f["frage"])[:100] or None,
                style=discord.TextStyle.paragraph if f.get("lang") else discord.TextStyle.short,
                required=f.get("pflicht", True), max_length=f.get("max", 1000 if f.get("lang") else 100))
            self.felder.append(ti)
            self.fragen.append(f["frage"])
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        async def antwort(e: discord.Embed, view: discord.ui.View | None = None) -> None:
            # In der DM wird die Fortfahren/Abbrechen-Nachricht ersetzt, im Server kommt eine private Antwort
            if interaction.guild is None and interaction.message:
                await interaction.response.edit_message(embed=e, view=view)
            elif view is not None:
                await interaction.response.send_message(embed=e, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=e, ephemeral=True)

        antworten = self.bisher + [{"frage": q, "antwort": f.value} for q, f in zip(self.fragen, self.felder)]
        seiten = fragen_seiten(self.bot)
        conf = self.bot.cfg.get("bewerbung", {})
        versatz = 2 if conf.get("einheit_waehlen", True) else 1   # Frage 1 ist die Division
        if self.teil + 1 < len(seiten):
            nummer = versatz + sum(len(x) for x in seiten[:self.teil + 1])
            liste = "\n".join(f"**{nummer + i}.** {f['frage']}" for i, f in enumerate(seiten[self.teil + 1]))
            e = u.embed(T("karriere.teil_fertig_titel", "✅ Teil {teil}/{gesamt} gespeichert", teil=self.teil + 1, gesamt=len(seiten)),
                        T("karriere.teil_fertig_text", "Als Nächstes kommen diese Fragen:\n{fragen}\n\n"
                          "Klicke auf **Weiter**, um fortzufahren. Du hast 30 Minuten Zeit.", fragen=liste))
            return await antwort(e, WeiterView(self.bot, self.guild_id, self.einheit, antworten, self.teil + 1, interaction.user.id))

        guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            return await antwort(u.fehler(T("karriere.server_weg", "Der Server ist nicht erreichbar.")))
        if (hinweis := await darf_bewerben(self.bot, guild.id, interaction.user.id)):
            return await antwort(u.warnung(hinweis))
        ch = await bewerbungs_kanal(self.bot, guild, self.einheit)
        if ch is None:
            return await antwort(u.fehler(T(
                "karriere.kein_kanal", "Der Bewerbungs-Kanal ist nicht eingerichtet. Melde dich beim Team.")))
        if conf.get("einheit_waehlen", True):
            antworten = [{"frage": einheit_frage_text(self.bot), "antwort": self.einheit}] + antworten
        bid = await self.bot.db.execute(
            "INSERT INTO bewerbungen (guild_id,user_id,einheit,antworten,zeit) VALUES (?,?,?,?,?)",
            guild.id, interaction.user.id, self.einheit, json.dumps(antworten, ensure_ascii=False), u.now())
        seiten_e = bewerbung_embeds(interaction.user, self.einheit, antworten, bid)
        view = discord.ui.View(timeout=None)
        view.add_item(BewerbungButton("ann", bid))
        view.add_item(BewerbungButton("abl", bid))
        rollen = self.bot.rechte.rollen_fuer_stufe(guild, "karriere")
        team = rollen[:3] if conf.get("team_pingen") else []
        ping = P("bewerbung_eingang", guild, *team)
        await ch.send(content=ping, embed=seiten_e[0], view=view,
                      allowed_mentions=discord.AllowedMentions(roles=True, everyone=True))
        for extra in seiten_e[1:]:
            await ch.send(embed=extra)
        fertig = u.ok(T("karriere.eingereicht", "Deine Bewerbung **#{nummer}** für **{einheit}** wurde eingereicht. "
                        "Du bekommst eine DM, sobald sie bearbeitet wurde.", nummer=bid, einheit=self.einheit),
                      T("karriere.eingereicht_titel", "Bewerbung eingereicht"))
        await antwort(fertig)


class DMBewerbungButton(discord.ui.DynamicItem[discord.ui.Button],
                        template=r"bw:bewdm:(?P<a>go|stop):(?P<g>\d+):(?P<e>\d+)"):
    """Fortfahren / Abbrechen in der DM. Funktioniert auch nach einem Neustart des Bots."""

    def __init__(self, aktion: str, guild_id: int, einheit_idx: int) -> None:
        self.aktion, self.guild_id, self.idx = aktion, guild_id, einheit_idx
        go = aktion == "go"
        super().__init__(discord.ui.Button(
            label=T("karriere.dm_knopf_fortfahren", "Bewerbung fortfahren") if go
            else T("karriere.dm_knopf_abbrechen", "Abbrechen"),
            emoji=(T("karriere.dm_knopf_fortfahren_emoji", "📝") if go else T("karriere.dm_knopf_abbrechen_emoji", "✖️")) or None,
            style=discord.ButtonStyle.success if go else discord.ButtonStyle.danger,
            custom_id=f"bw:bewdm:{aktion}:{guild_id}:{einheit_idx}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["a"], int(match["g"]), int(match["e"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        if self.aktion == "stop":
            return await interaction.response.edit_message(embed=u.embed(
                T("karriere.dm_abgebrochen_titel", "✖️ Bewerbung abgebrochen"),
                T("karriere.dm_abgebrochen", "Kein Problem. Du kannst dich jederzeit über das Karriere Center neu bewerben."),
                u.ROT), view=None)
        if (hinweis := await darf_bewerben(bot, self.guild_id, interaction.user.id)):
            return await interaction.response.edit_message(embed=u.warnung(hinweis), view=None)
        liste = einheiten_liste(bot)
        einheit = liste[self.idx] if self.idx < len(liste) else \
            bot.cfg.get("bewerbung", {}).get("standard_titel", "Bundeswehr")
        await interaction.response.send_modal(BewerbungModal(bot, self.guild_id, einheit))


def dm_start_view(guild_id: int, idx: int) -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    v.add_item(DMBewerbungButton("go", guild_id, idx))
    v.add_item(DMBewerbungButton("stop", guild_id, idx))
    return v


async def starte_bewerbung(interaction: discord.Interaction, einheit: str, idx: int) -> None:
    """Schickt die Fortfahren/Abbrechen-Nachricht per DM (oder öffnet direkt das Formular, falls abgeschaltet)."""
    bot = interaction.client
    conf = bot.cfg.get("bewerbung", {})
    if not conf.get("per_dm", True):
        return await interaction.response.send_modal(BewerbungModal(bot, interaction.guild_id, einheit))
    e = u.embed(T("karriere.dm_start_titel", "📝 Bewerbung – {einheit}", einheit=einheit), T(
        "karriere.dm_start_text", "Hallo {user}, du möchtest dich als **Divisionsleitung** der Division **{einheit}** auf **{server}** bewerben.\n\n"
        "Klicke auf **Bewerbung fortfahren**, um die Fragen zu beantworten (mehrere kurze Formulare), oder auf **Abbrechen**.",
        user=interaction.user.mention, einheit=einheit, server=interaction.guild.name))
    try:
        msg = await interaction.user.send(embed=e, view=dm_start_view(interaction.guild_id, idx))
    except (discord.Forbidden, discord.HTTPException):
        return await interaction.response.send_message(embed=u.fehler(T(
            "karriere.dm_zu", "Ich kann dir keine DM schicken. Erlaube in den Server-Einstellungen unter "
            "**Privatsphäre** Direktnachrichten von Servermitgliedern und versuche es erneut.")), ephemeral=True)
    antwort = u.ok(T("karriere.dm_gesendet", "Ich habe dir eine DM geschickt: {link}", link=msg.jump_url),
                   T("karriere.dm_gesendet_titel", "Schau in deine DMs"))
    if interaction.message and interaction.message.flags.ephemeral:
        await interaction.response.edit_message(embed=antwort, view=None)
    else:
        await interaction.response.send_message(embed=antwort, ephemeral=True)


def status_text(status: str) -> str:
    return {"offen": T("karriere.status_offen", "Offen"), "angenommen": T("karriere.status_angenommen", "angenommen"),
            "abgelehnt": T("karriere.status_abgelehnt", "abgelehnt")}.get(status, status)


def bewerbung_embeds(user: discord.abc.User, einheit: str, antworten: list[dict], bid: int,
                     status: str = "offen") -> list[discord.Embed]:
    """Eine Bewerbung mit vielen langen Antworten passt nicht in ein Embed (max. 6000 Zeichen) -> mehrere Seiten."""
    farbe = {"offen": u.GELB, "angenommen": u.GRUEN, "abgelehnt": u.ROT}.get(status, u.FARBE)
    seiten: list[list[tuple[str, str]]] = [[]]
    benutzt, budget = 0, 4200          # Seite 1 hat weniger Platz (Kopf, Status, Bearbeiter, Ablehn-Grund)
    for i, a in enumerate(antworten, 1):
        name, wert = f"{i}. {a['frage']}"[:256], (a["antwort"] or "–")[:1024]
        if seiten[-1] and benutzt + len(name) + len(wert) > budget:
            seiten.append([])
            benutzt, budget = 0, 5500
        seiten[-1].append((name, wert))
        benutzt += len(name) + len(wert)
    embeds = []
    for n, felder in enumerate(seiten):
        if n == 0:
            e = u.embed(T("karriere.embed_titel", "📨 Bewerbung #{nummer} – {einheit}", nummer=bid, einheit=einheit),
                        T("karriere.embed_text", "Von {user} (`{name}`)\nAccount erstellt: {erstellt}", user=user.mention,
                          name=user, erstellt=u.ts(user.created_at.timestamp(), 'R')), farbe)
            e.set_thumbnail(url=user.display_avatar.url)
        else:
            e = u.embed(T("karriere.embed_fortsetzung", "📨 Bewerbung #{nummer} – Fortsetzung ({seite}/{gesamt})",
                          nummer=bid, seite=n + 1, gesamt=len(seiten)), None, farbe)
        for name, wert in felder:
            e.add_field(name=name, value=wert, inline=False)
        if n == 0:
            e.add_field(name=T("karriere.feld_status", "Status"), value=status_text(status).capitalize())
        embeds.append(e)
    return embeds


def bewerbung_embed(user: discord.abc.User, einheit: str, antworten: list[dict], bid: int,
                    status: str = "offen") -> discord.Embed:
    """Erste Seite der Bewerbung (die mit den Knöpfen)."""
    return bewerbung_embeds(user, einheit, antworten, bid, status)[0]


class AblehnenModal(discord.ui.Modal, title="Ablehnen"):
    def __init__(self, cog: "Karriere", bid: int) -> None:
        super().__init__(title=T("karriere.ablehnen_titel", "Bewerbung ablehnen"))
        self.cog, self.bid = cog, bid
        self.grund = discord.ui.TextInput(label=T("karriere.ablehnen_grund", "Grund"), style=discord.TextStyle.paragraph,
                                          max_length=500)
        self.add_item(self.grund)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.bearbeite(interaction, self.bid, False, self.grund.value)


class BewerbungButton(discord.ui.DynamicItem[discord.ui.Button], template=r"bw:bew:(?P<a>ann|abl):(?P<id>\d+)"):
    def __init__(self, aktion: str, bid: int) -> None:
        self.aktion, self.bid = aktion, bid
        super().__init__(discord.ui.Button(
            label=T("karriere.knopf_annehmen", "Annehmen") if aktion == "ann" else T("karriere.knopf_ablehnen", "Ablehnen"),
            emoji=T("karriere.knopf_annehmen_emoji", "✅") if aktion == "ann" else T("karriere.knopf_ablehnen_emoji", "❌"),
            style=discord.ButtonStyle.success if aktion == "ann" else discord.ButtonStyle.danger,
            custom_id=f"bw:bew:{aktion}:{bid}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["a"], int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Karriere = interaction.client.get_cog("Karriere")
        if not interaction.client.rechte.hat_stufe(interaction.user, "karriere"):
            return await interaction.response.send_message(embed=u.fehler(T("karriere.nur_team", "Nur das Karriere Center darf das.")),
                                                           ephemeral=True)
        if self.aktion == "abl":
            return await interaction.response.send_modal(AblehnenModal(cog, self.bid))
        await cog.bearbeite(interaction, self.bid, True, None)


class EinheitWahl(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.liste = einheiten_liste(bot)
        opts = [discord.SelectOption(label=n, value=str(i),
                                     emoji=bot.rechte.einheiten[n].emoji if n in bot.rechte.einheiten else None)
                for i, n in enumerate(self.liste)][:25]
        sel = discord.ui.Select(placeholder=T("karriere.einheit_waehlen", "Division auswählen …"),
                                options=opts)
        sel.callback = self._gewaehlt
        self.sel = sel
        self.add_item(sel)

    async def _gewaehlt(self, interaction: discord.Interaction) -> None:
        idx = int(self.sel.values[0])
        await starte_bewerbung(interaction, self.liste[idx], idx)


class BewerbenView(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.start.label = T("karriere.knopf_bewerben", "Jetzt bewerben")
        self.start.emoji = T("karriere.knopf_bewerben_emoji", "📝") or None

    @discord.ui.button(label="Jetzt bewerben", style=discord.ButtonStyle.success, custom_id="bw:bew:start")
    async def start(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        conf = self.bot.cfg.get("bewerbung", {})
        if (hinweis := await darf_bewerben(self.bot, interaction.guild_id, interaction.user.id)):
            return await interaction.response.send_message(embed=u.warnung(hinweis), ephemeral=True)
        if conf.get("einheit_waehlen", True):
            await interaction.response.send_message(content=f"**1.** {einheit_frage_text(self.bot)}", view=EinheitWahl(self.bot), ephemeral=True)
        else:
            await starte_bewerbung(interaction, conf.get("standard_titel", "Bundeswehr"), 999)


# ----------------------------------------------------------------- Cog
class Karriere(commands.Cog):
    bewerbung = app_commands.Group(name="bewerbung", description="Bewerbungen (Karriere Center)", guild_only=True)
    ausbildung = app_commands.Group(name="ausbildung", description="Ausbildungen & Lehrgänge", guild_only=True)

    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(BewerbenView(self.bot))
        self.bot.add_dynamic_items(BewerbungButton, DMBewerbungButton)

    async def bearbeite(self, interaction: discord.Interaction, bid: int, annehmen: bool, grund: str | None) -> None:
        db = self.bot.db
        row = await db.fetchone("SELECT * FROM bewerbungen WHERE id=?", bid)
        if not row or row["status"] != "offen":
            return await interaction.response.send_message(embed=u.warnung(T("karriere.schon_bearbeitet", "Die Bewerbung wurde schon bearbeitet.")),
                                                           ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        status = "angenommen" if annehmen else "abgelehnt"
        await db.execute("UPDATE bewerbungen SET status=?, bearbeiter=?, grund=? WHERE id=?",
                         status, interaction.user.id, grund, bid)
        member = interaction.guild.get_member(row["user_id"])
        hinweis = ""
        if annehmen and member:
            conf = self.bot.cfg.get("bewerbung", {}).get("bei_annahme", {})
            rollen = [r for n in conf.get("rollen", []) if (r := self.bot.rechte.rolle(interaction.guild, n))]
            if rollen:
                await member.add_roles(*rollen, reason=f"Bewerbung #{bid} angenommen")
            e = self.bot.rechte.einheit(row["einheit"])
            if conf.get("in_einheit_eintragen", True) and e:
                personal = self.bot.get_cog("Personal")
                fehlend = await personal.einstellen_intern(member, e, int(conf.get("position", 0)), interaction.user)
                await personal.log(interaction.guild, member, T("karriere.log_einstellung", "Einstellung (Bewerbung)"),
                                   f"{e.emoji} **{e.name}** · #{bid}", interaction.user, u.GRUEN)
                if fehlend:
                    hinweis = "\n" + T("allgemein.fehlende_rollen", "⚠️ Fehlende Rollen: {rollen}", rollen=", ".join(fehlend))
        elif annehmen:
            hinweis = "\n" + T("karriere.nicht_mehr_da", "⚠️ Die Person ist nicht mehr auf dem Server.")
        # Nachricht aktualisieren
        if interaction.message:
            antworten = json.loads(row["antworten"])
            user = member or await self.bot.fetch_user(row["user_id"])
            e = bewerbung_embed(user, row["einheit"], antworten, bid, status)
            e.add_field(name=T("karriere.feld_bearbeiter", "Bearbeitet von"), value=interaction.user.mention)
            if grund:
                e.add_field(name=T("karriere.ablehnen_grund", "Grund"), value=grund[:1024], inline=False)
            await interaction.message.edit(embed=e, view=None)
        user = member or await self.bot.fetch_user(row["user_id"])
        werte = dict(einheit=row["einheit"], grund=grund or "–", user=user.mention, server=interaction.guild.name)
        if annehmen:
            dm = u.embed(T("karriere.dm_angenommen_titel", "📨 Bewerbung angenommen"), T(
                "karriere.dm_angenommen", "Deine Bewerbung als Divisionsleitung für **{einheit}** wurde **angenommen**.\n\n"
                "Herzlichen Glückwunsch! Das Team meldet sich bei dir.", **werte), u.GRUEN)
        else:
            dm = u.embed(T("karriere.dm_abgelehnt_titel", "📨 Bewerbung abgelehnt"), T(
                "karriere.dm_abgelehnt", "Deine Bewerbung für **{einheit}** wurde **abgelehnt**.\nGrund: {grund}\n\n"
                "Du kannst dich in ein paar Tagen erneut bewerben.", **werte), u.ROT)
        await u.dm(user, dm)
        await interaction.followup.send(embed=u.ok(T("karriere.bearbeitet_ok", "Bewerbung #{nummer} {status}.", nummer=bid,
                                                     status=status_text(status)) + hinweis), ephemeral=True)

    # ---------------------------------------------------------- /bewerbung
    @stufe("karriere")
    @bewerbung.command(name="panel", description="Postet das Bewerbungs-Panel mit Button")
    async def panel(self, interaction: discord.Interaction, kanal: discord.TextChannel | None = None) -> None:
        conf = self.bot.cfg.get("bewerbung", {})
        ch = kanal or interaction.channel
        e = u.embed(T("karriere.panel_titel", "📝 Bundeswehr Karriere Center"), T(
            "karriere.panel_text", "Du möchtest eine **Division** der **Bundeswehrkaserne Nienburg** leiten?\n"
            "Klicke auf **Jetzt bewerben**, wähle deine Division und beantworte die Fragen.\n"
            "Das Karriere Center meldet sich per DM bei dir."))
        if conf.get("panel_bild"):
            e.set_image(url=conf["panel_bild"])
        await ch.send(embed=e, view=BewerbenView(self.bot))
        await interaction.response.send_message(embed=u.ok(T("allgemein.panel_gepostet", "Panel in {kanal} gepostet.", kanal=ch.mention)), ephemeral=True)

    @stufe("karriere")
    @bewerbung.command(name="liste", description="Zeigt Bewerbungen")
    @app_commands.choices(status=[app_commands.Choice(name=s.capitalize(), value=s)
                                  for s in ("offen", "angenommen", "abgelehnt")])
    async def liste(self, interaction: discord.Interaction, status: str = "offen") -> None:
        rows = await self.bot.db.fetchall("SELECT * FROM bewerbungen WHERE guild_id=? AND status=? ORDER BY zeit DESC LIMIT 30",
                                          interaction.guild_id, status)
        zeilen = [f"`#{r['id']}` <@{r['user_id']}> – {r['einheit']} · {u.ts(r['zeit'], 'R')}" for r in rows]
        await interaction.response.send_message(
            embed=u.embed(T("karriere.liste_titel", "📨 Bewerbungen ({status})", status=status), "\n".join(zeilen) or T("allgemein.keine", "Keine.")), ephemeral=True)

    @stufe("karriere")
    @bewerbung.command(name="anzeigen", description="Zeigt eine Bewerbung im Detail")
    async def anzeigen(self, interaction: discord.Interaction, nummer: int) -> None:
        row = await self.bot.db.fetchone("SELECT * FROM bewerbungen WHERE id=? AND guild_id=?", nummer, interaction.guild_id)
        if not row:
            return await interaction.response.send_message(embed=u.fehler(T("allgemein.nicht_gefunden", "Nicht gefunden.")), ephemeral=True)
        user = interaction.guild.get_member(row["user_id"]) or await self.bot.fetch_user(row["user_id"])
        seiten = bewerbung_embeds(user, row["einheit"], json.loads(row["antworten"]), nummer, row["status"])
        view = None
        if row["status"] == "offen":
            view = discord.ui.View(timeout=None)
            view.add_item(BewerbungButton("ann", nummer))
            view.add_item(BewerbungButton("abl", nummer))
        await interaction.response.send_message(embed=seiten[0], view=view, ephemeral=True)
        for extra in seiten[1:]:
            await interaction.followup.send(embed=extra, ephemeral=True)

    # --------------------------------------------------------- /ausbildung
    @stufe("ausbilder")
    @ausbildung.command(name="eintragen", description="Trägt einen bestandenen Lehrgang ein")
    @app_commands.autocomplete(lehrgang=ac.lehrgang)
    async def eintragen(self, interaction: discord.Interaction, user: discord.Member, lehrgang: str,
                        bemerkung: str | None = None) -> None:
        try:
            await self.bot.db.execute(
                "INSERT INTO lehrgaenge (guild_id,user_id,lehrgang,ausbilder,zeit) VALUES (?,?,?,?,?)",
                interaction.guild_id, user.id, lehrgang, interaction.user.id, u.now())
        except Exception:  # noqa: BLE001 – UNIQUE
            return await interaction.response.send_message(embed=u.warnung(T("ausbildung.schon_eingetragen", "Ist schon eingetragen.")), ephemeral=True)
        conf = self.bot.cfg.get("ausbildung", {})
        hinweis = ""
        rolle_name = (conf.get("rollen_nach_lehrgang") or {}).get(lehrgang)
        if rolle_name and (rolle := self.bot.rechte.rolle(interaction.guild, rolle_name)):
            try:
                await user.add_roles(rolle, reason=f"Lehrgang {lehrgang}")
                hinweis = "\n" + T("ausbildung.rolle_vergeben", "Rolle {rolle} vergeben.", rolle=rolle.mention)
            except discord.Forbidden:
                hinweis = "\n" + T("ausbildung.rolle_fehler", "⚠️ Konnte Rolle nicht vergeben.")
        personal = self.bot.get_cog("Personal")
        await personal.log(interaction.guild, user, T("ausbildung.log_titel", "Lehrgang bestanden"),
                           T("ausbildung.log_text", "🎓 **{lehrgang}**", lehrgang=lehrgang) + (f"\n{bemerkung}" if bemerkung else ""), interaction.user, u.GRUEN)
        await u.dm(user, u.embed(T("ausbildung.dm_titel", "🎓 Lehrgang bestanden"), T("ausbildung.dm_text", "Glückwunsch! Du hast **{lehrgang}** bestanden.", lehrgang=lehrgang)))
        await interaction.response.send_message(embed=u.ok(T("ausbildung.bestanden_ok", "{user} hat **{lehrgang}** bestanden.", user=user.mention, lehrgang=lehrgang) + hinweis),
                                                ephemeral=True)

    @stufe("ausbilder")
    @ausbildung.command(name="entfernen", description="Entfernt einen Lehrgang")
    @app_commands.autocomplete(lehrgang=ac.lehrgang)
    async def entfernen(self, interaction: discord.Interaction, user: discord.Member, lehrgang: str) -> None:
        await self.bot.db.execute("DELETE FROM lehrgaenge WHERE guild_id=? AND user_id=? AND lehrgang=?",
                                  interaction.guild_id, user.id, lehrgang)
        await interaction.response.send_message(embed=u.ok(T("ausbildung.entfernt", "**{lehrgang}** bei {user} entfernt.", lehrgang=lehrgang, user=user.mention)), ephemeral=True)

    @stufe("jeder")
    @ausbildung.command(name="liste", description="Zeigt die Lehrgänge einer Person")
    async def liste_lehrgaenge(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        user = user or interaction.user
        rows = await self.bot.db.fetchall("SELECT * FROM lehrgaenge WHERE guild_id=? AND user_id=? ORDER BY zeit",
                                          interaction.guild_id, user.id)
        alle = self.bot.cfg.get("ausbildung", {}).get("lehrgaenge", [])
        hat = {r["lehrgang"]: r for r in rows}
        zeilen = [f"✅ **{l}** – {u.ts(hat[l]['zeit'], 'd')} (<@{hat[l]['ausbilder']}>)" if l in hat else f"⬜ {l}"
                  for l in alle]
        zeilen += [f"✅ **{l}**" for l in hat if l not in alle]
        await interaction.response.send_message(embed=u.embed(T("ausbildung.liste_titel", "🎓 Lehrgänge – {name}", name=user.display_name),
                                                              "\n".join(zeilen) or "–"), ephemeral=True)

    @stufe("ausbilder")
    @ausbildung.command(name="ankuendigen", description="Kündigt eine Ausbildung/einen Lehrgang an")
    @app_commands.autocomplete(lehrgang=ac.lehrgang)
    @app_commands.describe(zeitpunkt="z. B. 24.12.2026 18:00 oder 18:00")
    async def ankuendigen(self, interaction: discord.Interaction, lehrgang: str, zeitpunkt: str,
                          ort: str | None = None, ping: discord.Role | None = None) -> None:
        d = u.parse_datum(zeitpunkt)
        if not d:
            return await interaction.response.send_message(embed=u.fehler(T("allgemein.datum_ungueltig", "Ungültiges Datum.")), ephemeral=True)
        events = self.bot.get_cog("Events")
        await events.erstelle(interaction, "Ausbildung", T("ausbildung.event_titel", "🎓 {lehrgang}", lehrgang=lehrgang),
                              T("ausbildung.event_text", "Ausbilder: {user}", user=interaction.user.mention), ort, int(d.timestamp()), ping, None)

    # ------------------------------------------- /ausbildungs-ankuendigung
    @stufe("ausbilder")
    @app_commands.command(name="ausbildungs-ankuendigung",
                          description="Postet eine Ausbildungs-Ankündigung mit Rang, Pad, Uhrzeit und Server")
    @app_commands.guild_only()
    @app_commands.describe(rang="Welcher Rang wird ausgebildet? z. B. Ml1 / Gefreiter - Obergefreiter",
                           pad="Welches Ausbildungs-Pad? z. B. Pad 3",
                           uhrzeit="Wann geht es los? z. B. 19:15",
                           server="Server, auf dem die Ausbildung stattfindet (optional)",
                           ping="Rolle, die gepingt werden soll (z. B. Rekruten)",
                           kanal="Kanal für die Ankündigung (sonst dieser Kanal)")
    async def ausbildungs_ankuendigung(self, interaction: discord.Interaction,
                                       rang: app_commands.Range[str, 1, 100],
                                       pad: app_commands.Range[str, 1, 50],
                                       uhrzeit: app_commands.Range[str, 1, 50],
                                       server: app_commands.Range[str, 1, 100] | None = None,
                                       ping: discord.Role | None = None,
                                       kanal: discord.TextChannel | None = None) -> None:
        kanal = kanal or interaction.channel
        ausbilder = interaction.user

        kopf = T("ausbildung_ankuendigung.kopf", "# 🎓 Ausbildungszentrum der Bundeswehr")
        text = T("ausbildung_ankuendigung.text",
                 "Hört her, Rekruten! {ausbilder} lädt zur nächsten Ausbildung ein.\n"
                 "Alle wichtigen Details findet ihr unten. Seid pünktlich und kommt vorbereitet!",
                 ausbilder=ausbilder.mention)
        inhalt = "\n".join(x for x in (P("ausbildung_ankuendigung", interaction.guild, ping), kopf, text) if x)

        e = u.embed(T("ausbildung_ankuendigung.titel", "Ausbildungs-Infos"), None)
        e.add_field(name=T("ausbildung_ankuendigung.feld_rang", "⛑️ Ausbildungsrang"), value=rang, inline=False)
        e.add_field(name=T("ausbildung_ankuendigung.feld_pad", "#️⃣ Ausbildungs-Pad"), value=pad, inline=False)
        e.add_field(name=T("ausbildung_ankuendigung.feld_uhrzeit", "🕐 Uhrzeit"), value=uhrzeit, inline=False)
        e.add_field(name=T("ausbildung_ankuendigung.feld_ausbilder", "👨‍🏫 Ausbilder"),
                    value=ausbilder.mention, inline=False)
        if server:
            e.add_field(name=T("ausbildung_ankuendigung.feld_server", "💻 Server"), value=server, inline=False)

        try:
            await kanal.send(content=inhalt, embed=e,
                             allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True))
        except discord.HTTPException as ex:
            return await interaction.response.send_message(
                embed=u.fehler(T("allgemein.senden_fehler", "Senden fehlgeschlagen: {fehler}", fehler=ex)), ephemeral=True)
        await interaction.response.send_message(
            embed=u.ok(T("ausbildung_ankuendigung.ok", "Ankündigung in {kanal} gepostet.", kanal=kanal.mention)),
            ephemeral=True)


# ==========================================================================
#  MODUL: DIENST – Dienstzeiten und Abmeldungen
#  /dienst – Dienstzeiten erfassen  ·  /abmeldung – Urlaub, Krankheit …
# ==========================================================================

ZEITRAUM = [app_commands.Choice(name=T("dienst.woche", "Diese Woche"), value="woche"),
            app_commands.Choice(name=T("dienst.monat", "Dieser Monat"), value="monat"),
            app_commands.Choice(name=T("dienst.gesamt", "Gesamt"), value="gesamt")]


def zeitraum_start(z: str) -> int:
    jetzt = dt.datetime.now(u.TZ)
    if z == "woche":
        d = (jetzt - dt.timedelta(days=jetzt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif z == "monat":
        d = jetzt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return 0
    return int(d.timestamp())


class DienstPanel(discord.ui.View):
    def __init__(self, cog: "Dienst") -> None:
        super().__init__(timeout=None)
        self.cog = cog
        for knopf, key_l, def_l, key_e, def_e in (
                (self.start_btn, "dienst.knopf_start", "Dienst beginnen", "dienst.knopf_start_emoji", "🟢"),
                (self.ende_btn, "dienst.knopf_ende", "Dienst beenden", "dienst.knopf_ende_emoji", "🔴"),
                (self.zeit_btn, "dienst.knopf_zeit", "Meine Zeit", "dienst.knopf_zeit_emoji", "⏱️")):
            knopf.label = T(key_l, def_l)
            knopf.emoji = T(key_e, def_e) or None

    @discord.ui.button(label="Dienst beginnen", style=discord.ButtonStyle.success, custom_id="bw:dienst:start")
    async def start_btn(self, interaction: discord.Interaction, _):
        await self.cog.starte(interaction)

    @discord.ui.button(label="Dienst beenden", style=discord.ButtonStyle.danger, custom_id="bw:dienst:ende")
    async def ende_btn(self, interaction: discord.Interaction, _):
        await self.cog.beende(interaction, interaction.user)

    @discord.ui.button(label="Meine Zeit", style=discord.ButtonStyle.secondary, custom_id="bw:dienst:zeit")
    async def zeit_btn(self, interaction: discord.Interaction, _):
        await self.cog.zeige_statistik(interaction, interaction.user, "woche")


class Dienst(commands.Cog):
    dienst = app_commands.Group(name="dienst", description="Dienstzeiten", guild_only=True)
    abmeldung = app_commands.Group(name="abmeldung", description="Abmeldungen (Urlaub, Krankheit …)", guild_only=True)

    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(DienstPanel(self))
        self.aufraeumen.start()

    async def cog_unload(self) -> None:
        self.aufraeumen.cancel()

    @property
    def max_sek(self) -> int:
        return int(self.bot.cfg.get("dienst", {}).get("max_stunden", 12)) * 3600

    async def offen(self, gid: int, uid: int):
        return await self.bot.db.fetchone("SELECT * FROM dienst WHERE guild_id=? AND user_id=? AND ende IS NULL", gid, uid)

    async def summe(self, gid: int, uid: int | None, ab: int) -> dict[int, int]:
        rows = await self.bot.db.fetchall(
            "SELECT user_id, start, ende FROM dienst WHERE guild_id=? AND (ende IS NULL OR ende>=?)"
            + (" AND user_id=?" if uid else ""), *((gid, ab, uid) if uid else (gid, ab)))
        jetzt, out = u.now(), {}
        for r in rows:
            s = max(r["start"], ab)
            e = r["ende"] or jetzt
            out[r["user_id"]] = out.get(r["user_id"], 0) + max(0, e - s)
        return out

    # ----------------------------------------------------------- Aktionen
    async def starte(self, interaction: discord.Interaction) -> None:
        conf = self.bot.cfg.get("dienst", {})
        if conf.get("nur_soldaten", True):
            row = await self.bot.db.fetchone("SELECT 1 FROM soldaten WHERE guild_id=? AND user_id=? AND status='aktiv'",
                                             interaction.guild_id, interaction.user.id)
            if not row and not self.bot.rechte.hat_stufe(interaction.user, "admin"):
                return await interaction.response.send_message(
                    embed=u.fehler(T("dienst.nur_soldaten", "Nur eingetragene Soldaten können in den Dienst gehen.")), ephemeral=True)
        if (o := await self.offen(interaction.guild_id, interaction.user.id)):
            return await interaction.response.send_message(
                embed=u.warnung(T("dienst.schon_im_dienst", "Du bist schon seit {zeit} im Dienst.", zeit=u.ts(o['start'], 'R'))), ephemeral=True)
        await self.bot.db.execute("INSERT INTO dienst (guild_id,user_id,start) VALUES (?,?,?)",
                                  interaction.guild_id, interaction.user.id, u.now())
        rolle = self.bot.rechte.rolle(interaction.guild, conf.get("im_dienst_rolle", "")) if conf.get("im_dienst_rolle") else None
        if rolle:
            try:
                await interaction.user.add_roles(rolle, reason="Dienstbeginn")
            except discord.Forbidden:
                pass
        await u.send_log(self.bot, interaction.guild, "dienst",
                         u.embed(T("dienst.log_start_titel", "🟢 Dienstbeginn"),
                                 T("dienst.log_start", "{user} ist in den Dienst gegangen.", user=interaction.user.mention), u.GRUEN))
        await interaction.response.send_message(embed=u.ok(T("dienst.start_ok", "Du bist jetzt **im Dienst**. Viel Erfolg, Soldat!"),
                                                           T("dienst.start_titel", "Dienstbeginn")), ephemeral=True)

    async def beende(self, interaction: discord.Interaction, member: discord.Member, durch: discord.Member | None = None) -> None:
        o = await self.offen(interaction.guild_id, member.id)
        if not o:
            return await interaction.response.send_message(embed=u.warnung(T("dienst.kein_dienst", "Kein laufender Dienst.")), ephemeral=True)
        ende = min(u.now(), o["start"] + self.max_sek)
        await self.bot.db.execute("UPDATE dienst SET ende=? WHERE id=?", ende, o["id"])
        await self._rolle_weg(member)
        dauer = u.fmt_dauer(ende - o["start"])
        woche = (await self.summe(interaction.guild_id, member.id, zeitraum_start("woche"))).get(member.id, 0)
        await u.send_log(self.bot, interaction.guild, "dienst", u.embed(
            T("dienst.log_ende_titel", "🔴 Dienstende"),
            T("dienst.log_ende", "{user} hat den Dienst beendet. Dauer: **{dauer}**", user=member.mention, dauer=dauer)
            + ("\n" + T("dienst.log_beendet_durch", "Beendet durch {user}", user=durch.mention) if durch else ""), u.ROT))
        await interaction.response.send_message(
            embed=u.ok(T("dienst.ende_ok", "Dienst von {user} beendet.\nDauer: **{dauer}** · Diese Woche: **{woche}**",
                         user=member.mention, dauer=dauer, woche=u.fmt_dauer(woche)), T("dienst.ende_titel", "Dienstende")), ephemeral=True)

    async def _rolle_weg(self, member: discord.Member) -> None:
        name = self.bot.cfg.get("dienst", {}).get("im_dienst_rolle")
        rolle = self.bot.rechte.rolle(member.guild, name) if name else None
        if rolle and rolle in member.roles:
            try:
                await member.remove_roles(rolle, reason="Dienstende")
            except discord.Forbidden:
                pass

    async def zeige_statistik(self, interaction: discord.Interaction, user: discord.Member, zeitraum: str) -> None:
        gid = interaction.guild_id
        e = u.embed(T("dienst.statistik_titel", "⏱️ Dienstzeit – {name}", name=user.display_name))
        for name, z in ((c.name, c.value) for c in ZEITRAUM):
            e.add_field(name=name, value=u.fmt_dauer((await self.summe(gid, user.id, zeitraum_start(z))).get(user.id, 0)))
        anzahl = await self.bot.db.fetchone("SELECT COUNT(*) c FROM dienst WHERE guild_id=? AND user_id=?", gid, user.id)
        e.add_field(name=T("dienst.anzahl", "Dienste"), value=str(anzahl["c"]))
        if (o := await self.offen(gid, user.id)):
            e.add_field(name=T("dienst.status", "Status"), value=T("dienst.status_im_dienst", "🟢 Im Dienst seit {zeit}", zeit=u.ts(o['start'], 'R')))
        else:
            e.add_field(name=T("dienst.status", "Status"), value=T("dienst.status_ausser_dienst", "🔴 Außer Dienst"))
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ------------------------------------------------------------- /dienst
    @stufe("jeder")
    @dienst.command(name="start", description="Dienst beginnen")
    async def start(self, interaction: discord.Interaction) -> None:
        await self.starte(interaction)

    @stufe("jeder")
    @dienst.command(name="ende", description="Dienst beenden")
    async def ende(self, interaction: discord.Interaction) -> None:
        await self.beende(interaction, interaction.user)

    @stufe("jeder")
    @dienst.command(name="statistik", description="Dienstzeiten einer Person")
    async def statistik(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        await self.zeige_statistik(interaction, user or interaction.user, "woche")

    @stufe("jeder")
    @dienst.command(name="aktiv", description="Wer ist gerade im Dienst?")
    async def aktiv(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.fetchall("SELECT * FROM dienst WHERE guild_id=? AND ende IS NULL ORDER BY start",
                                          interaction.guild_id)
        zeilen = [T("dienst.aktiv_zeile", "🟢 {user} – seit {zeit}", user=f"<@{r['user_id']}>", zeit=u.ts(r['start'], 'R')) for r in rows]
        await interaction.response.send_message(
            embed=u.embed(T("dienst.aktiv_titel", "🪖 Im Dienst ({anzahl})", anzahl=len(rows)), "\n".join(zeilen) or T("dienst.niemand", "Niemand im Dienst.")))

    @stufe("jeder")
    @dienst.command(name="rangliste", description="Wer war am meisten im Dienst?")
    @app_commands.choices(zeitraum=ZEITRAUM)
    async def rangliste(self, interaction: discord.Interaction, zeitraum: str = "woche") -> None:
        daten = await self.summe(interaction.guild_id, None, zeitraum_start(zeitraum))
        top = sorted(daten.items(), key=lambda x: x[1], reverse=True)[:15]
        medaillen = [T("dienst.platz1", "🥇"), T("dienst.platz2", "🥈"), T("dienst.platz3", "🥉")]
        zeilen = [f"{medaillen[i] if i < 3 else f'`{i + 1}.`'} <@{uid}> – **{u.fmt_dauer(s)}**" for i, (uid, s) in enumerate(top)]
        name = next(c.name for c in ZEITRAUM if c.value == zeitraum)
        await interaction.response.send_message(embed=u.embed(T("dienst.rangliste_titel", "🏆 Dienst-Rangliste ({zeitraum})", zeitraum=name), "\n".join(zeilen) or T("dienst.keine_daten", "Keine Daten.")))

    @stufe("personal")
    @dienst.command(name="beenden", description="Beendet den Dienst einer anderen Person")
    async def zwangsende(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.beende(interaction, user, interaction.user)

    @stufe("admin")
    @dienst.command(name="panel", description="Postet ein Dienst-Panel mit Buttons")
    async def panel(self, interaction: discord.Interaction, kanal: discord.TextChannel | None = None) -> None:
        ch = kanal or interaction.channel
        await ch.send(embed=u.embed(T("dienst.panel_titel", "🪖 Dienststelle"), T("dienst.panel_text", "Melde dich hier zum Dienst an und ab.")), view=DienstPanel(self))
        await interaction.response.send_message(embed=u.ok(T("allgemein.panel_gepostet", "Panel in {kanal} gepostet.", kanal=ch.mention)), ephemeral=True)

    @stufe("admin")
    @dienst.command(name="zuruecksetzen", description="Löscht alle Dienstzeiten einer Person")
    async def zuruecksetzen(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.bot.db.execute("DELETE FROM dienst WHERE guild_id=? AND user_id=?", interaction.guild_id, user.id)
        await interaction.response.send_message(embed=u.ok(T("dienst.reset_ok", "Dienstzeiten von {user} gelöscht.", user=user.mention)), ephemeral=True)

    @stufe("personal")
    @dienst.command(name="nachtragen", description="Trägt Dienstzeit manuell nach (z. B. '2h30m')")
    async def nachtragen(self, interaction: discord.Interaction, user: discord.Member, dauer: str) -> None:
        sek = u.parse_dauer(dauer)
        if not sek:
            return await interaction.response.send_message(embed=u.fehler(T("dienst.dauer_ungueltig", "Ungültige Dauer, z. B. `2h30m`.")), ephemeral=True)
        jetzt = u.now()
        await self.bot.db.execute("INSERT INTO dienst (guild_id,user_id,start,ende) VALUES (?,?,?,?)",
                                  interaction.guild_id, user.id, jetzt - sek, jetzt)
        await interaction.response.send_message(embed=u.ok(T("dienst.nachgetragen", "**{dauer}** für {user} nachgetragen.", dauer=u.fmt_dauer(sek), user=user.mention)),
                                                ephemeral=True)

    # ---------------------------------------------------------- /abmeldung
    @stufe("jeder")
    @abmeldung.command(name="erstellen", description="Meldet dich für einen Zeitraum ab")
    @app_commands.describe(von="z. B. 10.11.2026", bis="z. B. 17.11.2026", grund="Urlaub, Krankheit, …")
    async def abm_erstellen(self, interaction: discord.Interaction, von: str, bis: str, grund: str) -> None:
        d_von, d_bis = u.parse_datum(von), u.parse_datum(bis)
        if not d_von or not d_bis:
            return await interaction.response.send_message(embed=u.fehler(T("abmeldung.datum_format", "Datum bitte als `TT.MM.JJJJ`.")), ephemeral=True)
        d_bis = d_bis.replace(hour=23, minute=59) if d_bis.hour == 0 and d_bis.minute == 0 else d_bis
        if d_bis < d_von:
            return await interaction.response.send_message(embed=u.fehler(T("abmeldung.bis_vor_von", "'bis' liegt vor 'von'.")), ephemeral=True)
        aid = await self.bot.db.execute(
            "INSERT INTO abmeldungen (guild_id,user_id,von,bis,grund,zeit) VALUES (?,?,?,?,?,?)",
            interaction.guild_id, interaction.user.id, int(d_von.timestamp()), int(d_bis.timestamp()), grund, u.now())
        e = u.embed(T("abmeldung.titel", "📅 Abmeldung #{nummer}", nummer=aid), T("abmeldung.text", "{user} ist abgemeldet.", user=interaction.user.mention), u.GELB)
        e.add_field(name=T("abmeldung.von", "Von"), value=u.ts(d_von.timestamp(), "D"))
        e.add_field(name=T("abmeldung.bis", "Bis"), value=u.ts(d_bis.timestamp(), "D"))
        e.add_field(name=T("abmeldung.grund", "Grund"), value=grund, inline=False)
        await u.send_log(self.bot, interaction.guild, "abmeldung", e, content=P("abmeldung", interaction.guild))
        await interaction.response.send_message(embed=u.ok(T("abmeldung.ok", "Abmeldung eingetragen.")), ephemeral=True)

    @stufe("jeder")
    @abmeldung.command(name="beenden", description="Beendet deine aktuelle Abmeldung vorzeitig")
    async def abm_beenden(self, interaction: discord.Interaction) -> None:
        await self.bot.db.execute("UPDATE abmeldungen SET aktiv=0, bis=? WHERE guild_id=? AND user_id=? AND aktiv=1",
                                  u.now(), interaction.guild_id, interaction.user.id)
        await u.send_log(self.bot, interaction.guild, "abmeldung",
                         u.embed(T("abmeldung.zurueck_titel", "📅 Zurückgemeldet"), T("abmeldung.zurueck_text", "{user} ist wieder da.", user=interaction.user.mention), u.GRUEN))
        await interaction.response.send_message(embed=u.ok(T("abmeldung.zurueck_ok", "Willkommen zurück.")), ephemeral=True)

    @stufe("jeder")
    @abmeldung.command(name="liste", description="Alle aktuell abgemeldeten Personen")
    async def abm_liste(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.fetchall("SELECT * FROM abmeldungen WHERE guild_id=? AND aktiv=1 ORDER BY bis",
                                          interaction.guild_id)
        zeilen = [T("abmeldung.zeile", "{user} – {von} bis {bis} · {grund}", user=f"<@{r['user_id']}>", von=u.ts(r['von'], 'd'),
                    bis=u.ts(r['bis'], 'd'), grund=r['grund']) for r in rows]
        await interaction.response.send_message(
            embed=u.embed(T("abmeldung.liste_titel", "📅 Abmeldungen ({anzahl})", anzahl=len(rows)), u.chunk_lines(zeilen or [T("abmeldung.niemand", "Niemand abgemeldet.")])[0]), ephemeral=True)

    @stufe("personal")
    @abmeldung.command(name="loeschen", description="Löscht eine Abmeldung")
    async def abm_loeschen(self, interaction: discord.Interaction, nummer: int) -> None:
        await self.bot.db.execute("UPDATE abmeldungen SET aktiv=0 WHERE id=? AND guild_id=?", nummer, interaction.guild_id)
        await interaction.response.send_message(embed=u.ok(T("abmeldung.geloescht", "Abmeldung #{nummer} gelöscht.", nummer=nummer)), ephemeral=True)

    # ------------------------------------------------------- Hintergrund
    @tasks.loop(minutes=5)
    async def aufraeumen(self) -> None:
        jetzt = u.now()
        # zu lange Dienste automatisch beenden
        rows = await self.bot.db.fetchall("SELECT * FROM dienst WHERE ende IS NULL AND start<?", jetzt - self.max_sek)
        for r in rows:
            await self.bot.db.execute("UPDATE dienst SET ende=? WHERE id=?", r["start"] + self.max_sek, r["id"])
            g = self.bot.get_guild(r["guild_id"])
            if g and (m := g.get_member(r["user_id"])):
                await self._rolle_weg(m)
                await u.dm(m, u.warnung(T("dienst.auto_ende", "Dein Dienst wurde automatisch beendet (Maximaldauer erreicht)."), T("dienst.auto_ende_titel", "Dienst")))
        # abgelaufene Abmeldungen
        await self.bot.db.execute("UPDATE abmeldungen SET aktiv=0 WHERE aktiv=1 AND bis<?", jetzt)

    @aufraeumen.before_loop
    async def _warten(self) -> None:
        await self.bot.wait_until_ready()


# ==========================================================================
#  MODUL: MODERATION – Warns, Timeouts, Bans, Clear ...
#  /mod – Verwarnungen, Timeouts, Kicks, Bans, Nachrichten löschen …
# ==========================================================================

class Moderation(commands.Cog):
    mod = app_commands.Group(name="mod", description="Moderation", guild_only=True)

    def __init__(self, bot) -> None:
        self.bot = bot

    async def _log(self, guild: discord.Guild, titel: str, user: discord.abc.User, von: discord.abc.User,
                   grund: str | None, farbe=None, extra: str = "") -> None:
        e = u.embed(titel, f"{user.mention} (`{user}` · {user.id})" + (f"\n{extra}" if extra else ""), farbe or u.ROT)
        e.add_field(name=T("mod.feld_moderator", "Moderator"), value=von.mention)
        e.add_field(name=T("mod.feld_grund", "Grund"), value=grund or "–", inline=False)
        await u.send_log(self.bot, guild, "mod", e)

    async def _pruefe(self, interaction: discord.Interaction, ziel: discord.Member) -> bool:
        if ziel.id == interaction.user.id:
            await interaction.response.send_message(embed=u.fehler(T("mod.nicht_selbst", "Nicht an dir selbst.")), ephemeral=True)
            return False
        if ziel.bot and ziel.id == self.bot.user.id:
            await interaction.response.send_message(embed=u.fehler(T("mod.nicht_bot", "Netter Versuch.")), ephemeral=True)
            return False
        if not u.kann_moderieren(interaction.user, ziel):
            await interaction.response.send_message(embed=u.fehler(T("mod.zu_hoch", "Diese Person steht gleich hoch oder über dir.")),
                                                    ephemeral=True)
            return False
        if not u.kann_moderieren(interaction.guild.me, ziel):
            await interaction.response.send_message(embed=u.fehler(T("mod.bot_zu_niedrig", "Meine Bot-Rolle steht unter dieser Person.")),
                                                    ephemeral=True)
            return False
        return True

    # -------------------------------------------------------------- Warns
    @stufe("support")
    @mod.command(name="warn", description="Verwarnt eine Person")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, grund: str) -> None:
        if not await self._pruefe(interaction, user):
            return
        wid = await self.bot.db.execute("INSERT INTO warns (guild_id,user_id,grund,von,zeit) VALUES (?,?,?,?,?)",
                                        interaction.guild_id, user.id, grund, interaction.user.id, u.now())
        anzahl = (await self.bot.db.fetchone("SELECT COUNT(*) c FROM warns WHERE guild_id=? AND user_id=?",
                                             interaction.guild_id, user.id))["c"]
        await u.dm(user, u.embed(T("mod.warn_dm_titel", "⚠️ Verwarnung"), T(
            "mod.warn_dm", "Du wurdest auf **{server}** verwarnt.\nGrund: {grund}\nVerwarnungen gesamt: **{anzahl}**",
            server=interaction.guild.name, grund=grund, anzahl=anzahl), u.GELB))
        await self._log(interaction.guild, T("mod.warn_log", "⚠️ Verwarnung #{nummer}", nummer=wid), user, interaction.user, grund,
                        u.GELB, T("mod.warn_gesamt", "Verwarnungen gesamt: **{anzahl}**", anzahl=anzahl))
        auto = ""
        for regel in sorted(self.bot.cfg.get("moderation", {}).get("warn_automatik", []),
                            key=lambda r: r["ab"], reverse=True):
            if anzahl == regel["ab"]:
                auto = await self._automatik(interaction, user, regel, anzahl)
                break
        await interaction.response.send_message(embed=u.ok(T("mod.warn_ok", "{user} verwarnt (**{anzahl}** gesamt).", user=user.mention, anzahl=anzahl) + " " + auto),
                                                ephemeral=True)

    async def _automatik(self, interaction, user: discord.Member, regel: dict, anzahl: int) -> str:
        grund = T("mod.auto_grund", "Automatisch: {anzahl} Verwarnungen", anzahl=anzahl)
        try:
            if regel["aktion"] == "timeout":
                sek = u.parse_dauer(regel.get("dauer", "1h")) or 3600
                await user.timeout(dt.timedelta(seconds=sek), reason=grund)
                await self._log(interaction.guild, T("mod.auto_timeout_log", "⏳ Auto-Timeout"), user, self.bot.user, grund)
                return "\n" + T("mod.auto_timeout", "➡️ Automatischer Timeout ({dauer}).", dauer=u.fmt_dauer(sek))
            if regel["aktion"] == "kick":
                await user.kick(reason=grund)
                await self._log(interaction.guild, T("mod.auto_kick_log", "👢 Auto-Kick"), user, self.bot.user, grund)
                return "\n" + T("mod.auto_kick", "➡️ Automatisch gekickt.")
            if regel["aktion"] == "ban":
                await user.ban(reason=grund)
                await self._log(interaction.guild, T("mod.auto_ban_log", "🔨 Auto-Bann"), user, self.bot.user, grund)
                return "\n" + T("mod.auto_ban", "➡️ Automatisch gebannt.")
        except discord.Forbidden:
            return "\n" + T("mod.auto_fehler", "⚠️ Automatik fehlgeschlagen (fehlende Rechte).")
        return ""

    @stufe("support")
    @mod.command(name="warns", description="Zeigt die Verwarnungen einer Person")
    async def warns(self, interaction: discord.Interaction, user: discord.Member) -> None:
        rows = await self.bot.db.fetchall("SELECT * FROM warns WHERE guild_id=? AND user_id=? ORDER BY zeit DESC",
                                          interaction.guild_id, user.id)
        zeilen = [f"`#{r['id']}` {u.ts(r['zeit'], 'd')} – {r['grund']} (<@{r['von']}>)" for r in rows]
        await interaction.response.send_message(embed=u.embed(T("mod.warns_titel", "⚠️ Verwarnungen – {name} ({anzahl})", name=user.display_name, anzahl=len(rows)),
                                                              u.chunk_lines(zeilen or [T("mod.keine_warns", "Keine.")])[0]), ephemeral=True)

    @stufe("moderator")
    @mod.command(name="warn-entfernen", description="Entfernt eine Verwarnung per Nummer")
    async def warn_entfernen(self, interaction: discord.Interaction, nummer: int) -> None:
        await self.bot.db.execute("DELETE FROM warns WHERE id=? AND guild_id=?", nummer, interaction.guild_id)
        await interaction.response.send_message(embed=u.ok(T("mod.warn_entfernt", "Verwarnung #{nummer} entfernt.", nummer=nummer)), ephemeral=True)

    @stufe("moderator")
    @mod.command(name="warns-leeren", description="Löscht alle Verwarnungen einer Person")
    async def warns_leeren(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.bot.db.execute("DELETE FROM warns WHERE guild_id=? AND user_id=?", interaction.guild_id, user.id)
        await interaction.response.send_message(embed=u.ok(T("mod.warns_geleert", "Alle Verwarnungen von {user} gelöscht.", user=user.mention)), ephemeral=True)

    # ------------------------------------------------------------ Strafen
    @stufe("support")
    @mod.command(name="timeout", description="Schickt jemanden in den Timeout (z. B. 10m, 1h, 2d)")
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, dauer: str, grund: str) -> None:
        if not await self._pruefe(interaction, user):
            return
        sek = u.parse_dauer(dauer)
        if not sek or sek > 28 * 86400:
            return await interaction.response.send_message(embed=u.fehler(T("mod.dauer_ungueltig", "Dauer z. B. `10m`, `1h`, max. 28 Tage.")),
                                                           ephemeral=True)
        await user.timeout(dt.timedelta(seconds=sek), reason=f"{interaction.user}: {grund}")
        await u.dm(user, u.embed(T("mod.timeout_dm_titel", "⏳ Timeout"), T("mod.timeout_dm", "Du bist für **{dauer}** im Timeout.\nGrund: {grund}",
                                                                     dauer=u.fmt_dauer(sek), grund=grund), u.GELB))
        await self._log(interaction.guild, T("mod.timeout_log", "⏳ Timeout"), user, interaction.user, grund, u.GELB,
                        T("mod.dauer", "Dauer: **{dauer}**", dauer=u.fmt_dauer(sek)))
        await interaction.response.send_message(embed=u.ok(T("mod.timeout_ok", "{user} ist für **{dauer}** im Timeout.", user=user.mention, dauer=u.fmt_dauer(sek))),
                                                ephemeral=True)

    @stufe("support")
    @mod.command(name="timeout-aufheben", description="Hebt einen Timeout auf")
    async def timeout_aufheben(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await user.timeout(None, reason=f"Aufgehoben von {interaction.user}")
        await self._log(interaction.guild, T("mod.timeout_aufgehoben_log", "✅ Timeout aufgehoben"), user, interaction.user, None, u.GRUEN)
        await interaction.response.send_message(embed=u.ok(T("mod.timeout_aufgehoben", "Timeout von {user} aufgehoben.", user=user.mention)), ephemeral=True)

    @stufe("moderator")
    @mod.command(name="kick", description="Kickt eine Person")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, grund: str) -> None:
        if not await self._pruefe(interaction, user):
            return
        await u.dm(user, u.embed(T("mod.kick_dm_titel", "👢 Gekickt"), T("mod.kick_dm", "Du wurdest von **{server}** gekickt.\nGrund: {grund}",
                                                                  server=interaction.guild.name, grund=grund), u.ROT))
        await user.kick(reason=f"{interaction.user}: {grund}")
        await self._log(interaction.guild, T("mod.kick_log", "👢 Kick"), user, interaction.user, grund)
        await interaction.response.send_message(embed=u.ok(T("mod.kick_ok", "{user} wurde gekickt.", user=user)), ephemeral=True)

    @stufe("moderator")
    @mod.command(name="ban", description="Bannt eine Person")
    @app_commands.describe(nachrichten_tage="Nachrichten der letzten X Tage löschen (0–7)")
    async def ban(self, interaction: discord.Interaction, user: discord.Member, grund: str,
                  nachrichten_tage: app_commands.Range[int, 0, 7] = 0) -> None:
        if not await self._pruefe(interaction, user):
            return
        await u.dm(user, u.embed(T("mod.ban_dm_titel", "🔨 Gebannt"), T(
            "mod.ban_dm", "Du wurdest von **{server}** gebannt.\nGrund: {grund}\n\n"
            "Einen Entbannungsantrag kannst du beim Entbannungsmanagement stellen.",
            server=interaction.guild.name, grund=grund), u.ROT))
        await user.ban(reason=f"{interaction.user}: {grund}", delete_message_seconds=nachrichten_tage * 86400)
        await self._log(interaction.guild, T("mod.ban_log", "🔨 Bann"), user, interaction.user, grund)
        await interaction.response.send_message(embed=u.ok(T("mod.ban_ok", "{user} wurde gebannt.", user=user)), ephemeral=True)

    @stufe("entbannung")
    @mod.command(name="unban", description="Entbannt eine Person per User-ID")
    async def unban(self, interaction: discord.Interaction, user_id: str, grund: str) -> None:
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=f"{interaction.user}: {grund}")
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message(embed=u.fehler(T("mod.unban_fehler", "User nicht gefunden oder nicht gebannt.")),
                                                           ephemeral=True)
        await self._log(interaction.guild, T("mod.unban_log", "🔓 Entbannung"), user, interaction.user, grund, u.GRUEN)
        await interaction.response.send_message(embed=u.ok(T("mod.unban_ok", "{user} wurde entbannt.", user=user)), ephemeral=True)

    # ----------------------------------------------------------- Kanäle
    @stufe("moderator")
    @mod.command(name="clear", description="Löscht Nachrichten im Kanal")
    async def clear(self, interaction: discord.Interaction, anzahl: app_commands.Range[int, 1, 100],
                    user: discord.Member | None = None) -> None:
        await interaction.response.defer(ephemeral=True)
        check = (lambda m: m.author.id == user.id) if user else None
        geloescht = await interaction.channel.purge(limit=anzahl, check=check) if check else \
            await interaction.channel.purge(limit=anzahl)
        await self._log(interaction.guild, T("mod.clear_log", "🧹 Nachrichten gelöscht"), interaction.user, interaction.user, None,
                        u.GELB, T("mod.clear_log_text", "**{anzahl}** Nachrichten in {kanal}", anzahl=len(geloescht),
                                  kanal=interaction.channel.mention))
        await interaction.followup.send(embed=u.ok(T("mod.clear_ok", "**{anzahl}** Nachrichten gelöscht.", anzahl=len(geloescht))), ephemeral=True)

    @stufe("moderator")
    @mod.command(name="slowmode", description="Setzt den Slowmode im Kanal (0 = aus)")
    async def slowmode(self, interaction: discord.Interaction, sekunden: app_commands.Range[int, 0, 21600]) -> None:
        await interaction.channel.edit(slowmode_delay=sekunden)
        await interaction.response.send_message(embed=u.ok(T("mod.slowmode_ok", "Slowmode: **{sekunden}s**", sekunden=sekunden)), ephemeral=True)

    @stufe("moderator")
    @mod.command(name="sperren", description="Sperrt einen Kanal für alle")
    async def sperren(self, interaction: discord.Interaction, kanal: discord.TextChannel | None = None,
                      grund: str | None = None) -> None:
        ch = kanal or interaction.channel
        ow = ch.overwrites_for(interaction.guild.default_role)
        ow.send_messages = False
        await ch.set_permissions(interaction.guild.default_role, overwrite=ow, reason=grund)
        await ch.send(embed=u.embed(T("mod.gesperrt_titel", "🔒 Kanal gesperrt"), grund or T("mod.gesperrt_text", "Dieser Kanal wurde gesperrt."), u.ROT))
        await interaction.response.send_message(embed=u.ok(T("mod.gesperrt_ok", "{kanal} gesperrt.", kanal=ch.mention)), ephemeral=True)

    @stufe("moderator")
    @mod.command(name="entsperren", description="Entsperrt einen Kanal")
    async def entsperren(self, interaction: discord.Interaction, kanal: discord.TextChannel | None = None) -> None:
        ch = kanal or interaction.channel
        ow = ch.overwrites_for(interaction.guild.default_role)
        ow.send_messages = None
        await ch.set_permissions(interaction.guild.default_role, overwrite=ow)
        await ch.send(embed=u.embed(T("mod.entsperrt_titel", "🔓 Kanal entsperrt"), None, u.GRUEN))
        await interaction.response.send_message(embed=u.ok(T("mod.entsperrt_ok", "{kanal} entsperrt.", kanal=ch.mention)), ephemeral=True)

    @stufe("moderator")
    @mod.command(name="nick", description="Ändert den Nicknamen einer Person")
    async def nick(self, interaction: discord.Interaction, user: discord.Member,
                   name: app_commands.Range[str, 1, 32] | None = None) -> None:
        if not await self._pruefe(interaction, user):
            return
        await user.edit(nick=name)
        await interaction.response.send_message(embed=u.ok(T("mod.nick_ok", "Nickname von {user} → **{name}**", user=user.mention, name=name or "zurückgesetzt")),
                                                ephemeral=True)

    @stufe("moderator")
    @mod.command(name="rolle", description="Gibt oder entfernt eine Rolle")
    @app_commands.choices(aktion=[app_commands.Choice(name="Geben", value="add"),
                                  app_commands.Choice(name="Entfernen", value="del")])
    async def rolle(self, interaction: discord.Interaction, user: discord.Member, aktion: str, rolle: discord.Role) -> None:
        if rolle >= interaction.user.top_role and interaction.guild.owner_id != interaction.user.id:
            return await interaction.response.send_message(embed=u.fehler(T("mod.rolle_zu_hoch", "Diese Rolle steht über deiner höchsten Rolle.")),
                                                           ephemeral=True)
        if aktion == "add":
            await user.add_roles(rolle, reason=f"von {interaction.user}")
        else:
            await user.remove_roles(rolle, reason=f"von {interaction.user}")
        await self._log(interaction.guild, T("mod.rolle_gegeben_log", "🏷️ Rolle gegeben") if aktion == "add" else T("mod.rolle_entfernt_log", "🏷️ Rolle entfernt"), user,
                        interaction.user, None, u.FARBE, rolle.mention)
        await interaction.response.send_message(embed=u.ok(T("mod.rolle_gegeben", "{rolle} an {user} gegeben.", rolle=rolle.mention, user=user.mention)
                                                     if aktion == "add" else
                                                     T("mod.rolle_entfernt", "{rolle} von {user} entfernt.", rolle=rolle.mention, user=user.mention)), ephemeral=True)


# ==========================================================================
#  MODUL: TICKETS – Ticketsystem
#  Ticketsystem mit Auswahlmenü, Übernehmen-/Schließen-Buttons und Transkript
# ==========================================================================

def ticket_arten(bot) -> list[dict]:
    return bot.cfg.get("tickets", {}).get("arten", [])


class TicketGrundModal(discord.ui.Modal):
    def __init__(self, cog: "Tickets", art: dict) -> None:
        super().__init__(title=T("tickets.modal_titel", "Ticket – {art}", art=art['name'])[:45])
        self.cog, self.art = cog, art
        self.grund = discord.ui.TextInput(label=T("tickets.modal_frage", "Worum geht es?"), style=discord.TextStyle.paragraph, max_length=1000)
        self.add_item(self.grund)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.oeffne(interaction, self.art, self.grund.value)


class TicketPanel(discord.ui.View):
    def __init__(self, cog: "Tickets") -> None:
        super().__init__(timeout=None)
        self.cog = cog
        opts = [discord.SelectOption(label=a["name"], value=a["name"], emoji=a.get("emoji"),
                                     description=a.get("beschreibung", "")[:100] or None)
                for a in ticket_arten(cog.bot)][:25] or [discord.SelectOption(label="Support")]
        sel = discord.ui.Select(placeholder=T("tickets.auswahl", "Wähle eine Ticket-Art …"), options=opts, custom_id="bw:ticket:panel")
        sel.callback = self._wahl
        self.add_item(sel)

    async def _wahl(self, interaction: discord.Interaction) -> None:
        name = interaction.data["values"][0]
        art = next((a for a in ticket_arten(self.cog.bot) if a["name"] == name), {"name": name, "team": ["support"]})
        await interaction.response.send_modal(TicketGrundModal(self.cog, art))
        # Auswahl zurücksetzen
        try:
            await interaction.message.edit(view=TicketPanel(self.cog))
        except discord.HTTPException:
            pass


class SchliessenModal(discord.ui.Modal, title="Ticket"):
    def __init__(self, cog: "Tickets") -> None:
        super().__init__(title=T("tickets.schliessen_titel", "Ticket schließen"))
        self.cog = cog
        self.grund = discord.ui.TextInput(label=T("tickets.schliessen_grund", "Grund (optional)"), required=False,
                                          max_length=500)
        self.add_item(self.grund)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.schliesse(interaction, self.grund.value or None)


class TicketSteuerung(discord.ui.View):
    def __init__(self, cog: "Tickets") -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.claim.label = T("tickets.knopf_uebernehmen", "Übernehmen")
        self.claim.emoji = T("tickets.knopf_uebernehmen_emoji", "🙋") or None
        self.close.label = T("tickets.knopf_schliessen", "Schließen")
        self.close.emoji = T("tickets.knopf_schliessen_emoji", "🔒") or None

    @discord.ui.button(label="Übernehmen", style=discord.ButtonStyle.primary, custom_id="bw:ticket:claim")
    async def claim(self, interaction: discord.Interaction, _):
        await self.cog.uebernehme(interaction)

    @discord.ui.button(label="Schließen", style=discord.ButtonStyle.danger, custom_id="bw:ticket:close")
    async def close(self, interaction: discord.Interaction, _):
        if not await self.cog.ist_team(interaction) and not await self.cog.ist_ersteller(interaction):
            return await interaction.response.send_message(embed=u.fehler(T("befehle.keine_berechtigung_titel", "Keine Berechtigung")), ephemeral=True)
        await interaction.response.send_modal(SchliessenModal(self.cog))


class Tickets(commands.Cog):
    ticket = app_commands.Group(name="ticket", description="Ticketsystem", guild_only=True)

    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(TicketPanel(self))
        self.bot.add_view(TicketSteuerung(self))

    async def _row(self, channel_id: int):
        return await self.bot.db.fetchone("SELECT * FROM tickets WHERE channel_id=? AND offen=1", channel_id)

    def _team_stufen(self, art_name: str) -> list[str]:
        art = next((a for a in ticket_arten(self.bot) if a["name"] == art_name), None)
        return (art or {}).get("team", ["support"])

    async def ist_team(self, interaction: discord.Interaction) -> bool:
        row = await self._row(interaction.channel_id)
        stufen = self._team_stufen(row["art"]) if row else ["support"]
        return any(self.bot.rechte.hat_stufe(interaction.user, s) for s in stufen)

    async def ist_ersteller(self, interaction: discord.Interaction) -> bool:
        row = await self._row(interaction.channel_id)
        return bool(row and row["user_id"] == interaction.user.id)

    async def kategorie_fuer(self, g: discord.Guild, art: dict) -> discord.CategoryChannel | None:
        """Reihenfolge: /setup kategorie mit art  ->  kategorie: in der config.yaml (wird bei Bedarf erstellt)
        ->  allgemeine Ticket-Kategorie."""
        kuerzel = art.get("kuerzel", art["name"])
        kid = await self.bot.db.get_setting(g.id, f"kategorie_ticket_{kuerzel}")
        if kid and isinstance(kat := g.get_channel(int(kid)), discord.CategoryChannel):
            return kat
        wunsch = str(art.get("kategorie") or "").strip()
        if wunsch:
            kat = g.get_channel(int(wunsch)) if wunsch.isdigit() else \
                discord.utils.find(lambda c: c.name.lower() == wunsch.lower(), g.categories)
            if kat is None and not wunsch.isdigit():
                ow = {g.default_role: discord.PermissionOverwrite(view_channel=False),
                      g.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)}
                for st in art.get("team", ["support"]):
                    for r in self.bot.rechte.rollen_fuer_stufe(g, st):
                        ow[r] = discord.PermissionOverwrite(view_channel=True)
                try:
                    kat = await g.create_category(wunsch, overwrites=ow, reason=f"Ticket-Kategorie für {art['name']}")
                except discord.HTTPException:
                    kat = None
            if isinstance(kat, discord.CategoryChannel):
                await self.bot.db.set_setting(g.id, f"kategorie_ticket_{kuerzel}", kat.id)
                return kat
        kid = await self.bot.db.get_setting(g.id, "kategorie_ticket")
        kat = g.get_channel(int(kid)) if kid else None
        return kat if isinstance(kat, discord.CategoryChannel) else None

    # ------------------------------------------------------------ Öffnen
    async def oeffne(self, interaction: discord.Interaction, art: dict, grund: str) -> None:
        g = interaction.guild
        conf = self.bot.cfg.get("tickets", {})
        offen = await self.bot.db.fetchall("SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND offen=1",
                                           g.id, interaction.user.id)
        offen = [r for r in offen if g.get_channel(r["channel_id"])]
        if len(offen) >= conf.get("max_pro_user", 2):
            return await interaction.response.send_message(
                embed=u.warnung(T("tickets.schon_offen", "Du hast schon offene Tickets: {tickets}",
                                   tickets=", ".join(f"<#{r['channel_id']}>" for r in offen))),
                ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        kat = await self.kategorie_fuer(g, art)
        nummer = int(await self.bot.db.get_setting(g.id, "ticket_zaehler", 0)) + 1
        await self.bot.db.set_setting(g.id, "ticket_zaehler", nummer)

        team = []
        for s in art.get("team", ["support"]):
            team += self.bot.rechte.rollen_fuer_stufe(g, s)
        ow = {g.default_role: discord.PermissionOverwrite(view_channel=False),
              g.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True,
                                                read_message_history=True, attach_files=True),
              interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                            read_message_history=True, attach_files=True)}
        for r in set(team):
            ow[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        name = f"{art.get('kuerzel', art['name'][:8]).lower()}-{nummer:04d}".replace(" ", "-")
        ch = await g.create_text_channel(name, category=kat,
                                         overwrites=ow, topic=f"Ticket von {interaction.user} · {art['name']}")
        await self.bot.db.execute("INSERT INTO tickets (channel_id,guild_id,user_id,art,nummer,zeit) VALUES (?,?,?,?,?,?)",
                                  ch.id, g.id, interaction.user.id, art["name"], nummer, u.now())
        e = u.embed(T("tickets.ticket_titel", "{emoji} Ticket #{nummer} – {art}", emoji=art.get("emoji", "🎫"),
                      nummer=f"{nummer:04d}", art=art["name"]),
                    art.get("willkommen") or T("tickets.ticket_text", "Danke für dein Ticket! Das Team meldet sich gleich bei dir."))
        e.add_field(name=T("tickets.feld_ersteller", "Erstellt von"), value=interaction.user.mention)
        e.add_field(name=T("tickets.feld_anliegen", "Anliegen"), value=grund[:1024], inline=False)
        team_ping = list(set(team))[:5] if conf.get("team_pingen", True) else []
        ping = P("ticket_erstellt", g, interaction.user, *team_ping)
        await ch.send(content=ping, embed=e, view=TicketSteuerung(self),
                      allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True))
        await interaction.followup.send(embed=u.ok(T("tickets.erstellt_ok", "Dein Ticket: {kanal}", kanal=ch.mention)),
                                        ephemeral=True)

    async def uebernehme(self, interaction: discord.Interaction) -> None:
        if not await self.ist_team(interaction):
            return await interaction.response.send_message(embed=u.fehler(T("tickets.nur_team", "Nur das Team kann Tickets übernehmen.")),
                                                           ephemeral=True)
        row = await self._row(interaction.channel_id)
        if not row:
            return await interaction.response.send_message(embed=u.fehler(T("tickets.kein_ticket", "Das ist kein Ticket.")), ephemeral=True)
        if row["uebernommen"]:
            return await interaction.response.send_message(
                embed=u.warnung(T("tickets.schon_uebernommen", "Schon übernommen von {user}.", user=f"<@{row['uebernommen']}>")), ephemeral=True)
        await self.bot.db.execute("UPDATE tickets SET uebernommen=? WHERE channel_id=?", interaction.user.id,
                                  interaction.channel_id)
        await interaction.response.send_message(embed=u.embed(T("tickets.uebernommen_titel", "🙋 Ticket übernommen"), T(
            "tickets.uebernommen_text", "{user} kümmert sich um dein Anliegen.", user=interaction.user.mention)))

    async def schliesse(self, interaction: discord.Interaction, grund: str | None) -> None:
        row = await self._row(interaction.channel_id)
        if not row:
            return await interaction.response.send_message(embed=u.fehler(T("tickets.kein_ticket", "Das ist kein Ticket.")), ephemeral=True)
        await interaction.response.send_message(embed=u.embed(T("tickets.wird_geschlossen", "🔒 Ticket wird geschlossen …"), grund))
        ch = interaction.channel
        zeilen = [f"Ticket #{row['nummer']:04d} – {row['art']} – erstellt von {row['user_id']}", "=" * 60]
        async for m in ch.history(limit=None, oldest_first=True):
            inhalt = m.content or ""
            if m.embeds:
                inhalt += " " + " | ".join(f"[Embed: {e.title or ''} {e.description or ''}]" for e in m.embeds)
            if m.attachments:
                inhalt += " " + " ".join(a.url for a in m.attachments)
            zeilen.append(f"[{m.created_at.astimezone(u.TZ):%d.%m.%Y %H:%M}] {m.author}: {inhalt}")
        datei = io.BytesIO("\n".join(zeilen).encode("utf-8"))
        await self.bot.db.execute("UPDATE tickets SET offen=0 WHERE channel_id=?", ch.id)
        e = u.embed(T("tickets.geschlossen_titel", "🎫 Ticket #{nummer} geschlossen", nummer=f"{row['nummer']:04d}"),
                    T("tickets.geschlossen_art", "Art: **{art}**", art=row['art']))
        e.add_field(name=T("tickets.feld_ersteller", "Erstellt von"), value=f"<@{row['user_id']}>")
        e.add_field(name=T("tickets.feld_geschlossen_von", "Geschlossen von"), value=interaction.user.mention)
        if row["uebernommen"]:
            e.add_field(name=T("tickets.feld_bearbeiter", "Bearbeitet von"), value=f"<@{row['uebernommen']}>")
        e.add_field(name=T("tickets.feld_grund", "Grund"), value=grund or "–", inline=False)
             await u.send_log(self.bot, interaction.guild, "ticket", e)

        ersteller = interaction.guild.get_member(row["user_id"])
        if ersteller and self.bot.cfg.get("tickets", {}).get("transkript_an_user", True):
                        try:
                await ersteller.send(embed=e)


    # ----------------------------------------------------------- /ticket
    @stufe("admin")
    @ticket.command(name="panel", description="Postet das Ticket-Panel")
    async def panel(self, interaction: discord.Interaction, kanal: discord.TextChannel | None = None) -> None:
        ch = kanal or interaction.channel
        arten = "\n".join(f"{a.get('emoji', '🎫')} **{a['name']}** – {a.get('beschreibung', '')}" for a in ticket_arten(self.bot))
        e = u.embed(T("tickets.panel_titel", "🎫 Support & Tickets"), T(
            "tickets.panel_text", "Wähle unten aus, worum es geht. Ein Teammitglied kümmert sich schnellstmöglich darum.\n\n{arten}",
            arten=arten))
        await ch.send(embed=e, view=TicketPanel(self))
        await interaction.response.send_message(embed=u.ok(T("allgemein.panel_gepostet", "Panel in {kanal} gepostet.", kanal=ch.mention)), ephemeral=True)

    @stufe("support")
    @ticket.command(name="schliessen", description="Schließt das aktuelle Ticket")
    async def schliessen(self, interaction: discord.Interaction, grund: str | None = None) -> None:
        await self.schliesse(interaction, grund)

    @stufe("support")
    @ticket.command(name="hinzufuegen", description="Fügt jemanden zum Ticket hinzu")
    async def hinzufuegen(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await self._row(interaction.channel_id):
            return await interaction.response.send_message(embed=u.fehler(T("tickets.kein_ticket", "Das ist kein Ticket.")), ephemeral=True)
        await interaction.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(embed=u.ok(T("tickets.hinzugefuegt", "{user} wurde hinzugefügt.", user=user.mention)))

    @stufe("support")
    @ticket.command(name="entfernen", description="Entfernt jemanden aus dem Ticket")
    async def entfernen(self, interaction: discord.Interaction, user: discord.Member) -> None:
        if not await self._row(interaction.channel_id):
            return await interaction.response.send_message(embed=u.fehler(T("tickets.kein_ticket", "Das ist kein Ticket.")), ephemeral=True)
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(embed=u.ok(T("tickets.entfernt", "{user} wurde entfernt.", user=user.mention)))

    @stufe("support")
    @ticket.command(name="umbenennen", description="Benennt das Ticket um")
    async def umbenennen(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 90]) -> None:
        if not await self._row(interaction.channel_id):
            return await interaction.response.send_message(embed=u.fehler(T("tickets.kein_ticket", "Das ist kein Ticket.")), ephemeral=True)
        await interaction.channel.edit(name=name)
        await interaction.response.send_message(embed=u.ok(T("tickets.umbenannt", "Umbenannt in **{name}**.", name=name)), ephemeral=True)

    @stufe("support")
    @ticket.command(name="uebernehmen", description="Übernimmt das aktuelle Ticket")
    async def uebernehmen_cmd(self, interaction: discord.Interaction) -> None:
        await self.uebernehme(interaction)


# ==========================================================================
#  MODUL: EVENTS – Events, Einsätze, Appelle
#  /event – Events, Einsätze, Übungen mit Zu-/Absage  ·  /appell – Anwesenheitskontrolle
# ==========================================================================

STATUS = ("ja", "vl", "nein")


def arten() -> dict[str, str]:
    """Event-Arten und ihre Symbole (änderbar hier im Code)."""
    return {"Event": T("events.symbol_event", "🎉"), "Einsatz": T("events.symbol_einsatz", "🚨"),
            "Übung": T("events.symbol_uebung", "🎯"), "Ausbildung": T("events.symbol_ausbildung", "🎓"),
            "Besprechung": T("events.symbol_besprechung", "📋"), "Parade": T("events.symbol_parade", "🎖️")}


def status_info(s: str) -> tuple[str, str, discord.ButtonStyle]:
    return {"ja": (T("events.knopf_zusagen", "Zusagen"), T("events.knopf_zusagen_emoji", "✅"), discord.ButtonStyle.success),
            "vl": (T("events.knopf_vielleicht", "Vielleicht"), T("events.knopf_vielleicht_emoji", "❔"),
                   discord.ButtonStyle.secondary),
            "nein": (T("events.knopf_absagen", "Absagen"), T("events.knopf_absagen_emoji", "❌"),
                     discord.ButtonStyle.danger)}[s]


class EventButton(discord.ui.DynamicItem[discord.ui.Button], template=r"bw:ev:(?P<s>ja|vl|nein):(?P<id>\d+)"):
    def __init__(self, status: str, eid: int) -> None:
        self.status, self.eid = status, eid
        label, emoji, style = status_info(status)
        super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style, custom_id=f"bw:ev:{status}:{eid}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["s"], int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Events = interaction.client.get_cog("Events")
        await cog.antwort(interaction, self.eid, self.status)


class AppellButton(discord.ui.DynamicItem[discord.ui.Button], template=r"bw:ap:(?P<id>\d+)"):
    def __init__(self, aid: int) -> None:
        self.aid = aid
        super().__init__(discord.ui.Button(label=T("appell.knopf", "Anwesend melden"), emoji=T("appell.knopf_emoji", "🫡") or None, style=discord.ButtonStyle.success,
                                           custom_id=f"bw:ap:{aid}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        row = await bot.db.fetchone("SELECT * FROM appelle WHERE id=?", self.aid)
        if not row or not row["aktiv"]:
            return await interaction.response.send_message(embed=u.warnung(T("appell.beendet", "Dieser Appell ist beendet.")), ephemeral=True)
        await bot.db.execute("INSERT OR IGNORE INTO appell_anwesend (appell_id,user_id,zeit) VALUES (?,?,?)",
                             self.aid, interaction.user.id, u.now())
        await interaction.response.send_message(embed=u.ok(T("appell.gemeldet", "Anwesenheit gemeldet. 🫡")), ephemeral=True)


def event_view(eid: int) -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    for s in STATUS:
        v.add_item(EventButton(s, eid))
    return v


class Events(commands.Cog):
    event = app_commands.Group(name="event", description="Events, Einsätze & Übungen", guild_only=True)
    appell = app_commands.Group(name="appell", description="Appelle / Anwesenheit", guild_only=True)

    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_dynamic_items(EventButton, AppellButton)
        self.ticker.start()

    async def cog_unload(self) -> None:
        self.ticker.cancel()

    # ----------------------------------------------------------- Embeds
    async def event_embed(self, row) -> discord.Embed:
        teil = await self.bot.db.fetchall("SELECT * FROM event_teilnehmer WHERE event_id=?", row["id"])
        gruppen = {s: [f"<@{t['user_id']}>" for t in teil if t["status"] == s] for s in STATUS}
        emoji = arten().get(row["art"], "📅")
        e = u.embed(T("events.embed_titel", "{emoji} {art}: {titel}", emoji=emoji, art=row['art'], titel=row['titel']),
                    row["beschreibung"] or None,
                    u.ROT if row["art"] == "Einsatz" else u.FARBE)
        e.add_field(name=T("events.feld_zeit", "🕒 Zeitpunkt"), value=f"{u.ts(row['zeitpunkt'], 'F')}\n({u.ts(row['zeitpunkt'], 'R')})")
        if row["ort"]:
            e.add_field(name=T("events.feld_ort", "📍 Ort"), value=row["ort"])
        e.add_field(name=T("events.feld_leitung", "👤 Leitung"), value=f"<@{row['ersteller']}>")
        for s in STATUS:
            label, em, _ = status_info(s)
            liste = gruppen[s]
            e.add_field(name=f"{em} {label} ({len(liste)})", value=("\n".join(liste)[:1024]) or "–", inline=True)
        e.set_footer(text=f"Event #{row['id']} · {u.FOOTER}")
        if not row["aktiv"]:
            e.title = T("events.beendet_titel", "[ABGESAGT/BEENDET] {titel}", titel=e.title)
            e.color = discord.Color.dark_grey()
        return e

    async def erstelle(self, interaction: discord.Interaction, art: str, titel: str, beschreibung: str | None,
                       ort: str | None, zeitpunkt: int, ping: discord.Role | None,
                       kanal: discord.TextChannel | None) -> None:
        if not kanal:
            cid = await self.bot.db.get_setting(interaction.guild_id, "kanal_events")
            kanal = interaction.guild.get_channel(int(cid)) if cid else interaction.channel
        eid = await self.bot.db.execute(
            "INSERT INTO events (guild_id,channel_id,art,titel,beschreibung,ort,zeitpunkt,ersteller) VALUES (?,?,?,?,?,?,?,?)",
            interaction.guild_id, kanal.id, art, titel, beschreibung, ort, zeitpunkt, interaction.user.id)
        row = await self.bot.db.fetchone("SELECT * FROM events WHERE id=?", eid)
        msg = await kanal.send(content=P("event_erstellt", interaction.guild, ping), embed=await self.event_embed(row),
                               view=event_view(eid), allowed_mentions=discord.AllowedMentions(roles=True, everyone=True))
        await self.bot.db.execute("UPDATE events SET message_id=? WHERE id=?", msg.id, eid)
        await interaction.response.send_message(embed=u.ok(T("events.erstellt_ok", "{art} **#{nummer}** erstellt: {link}", art=art, nummer=eid, link=msg.jump_url)), ephemeral=True)

    async def antwort(self, interaction: discord.Interaction, eid: int, status: str) -> None:
        row = await self.bot.db.fetchone("SELECT * FROM events WHERE id=?", eid)
        if not row or not row["aktiv"]:
            return await interaction.response.send_message(embed=u.warnung(T("events.nicht_aktiv", "Dieses Event ist nicht mehr aktiv.")),
                                                           ephemeral=True)
        await self.bot.db.execute("INSERT OR REPLACE INTO event_teilnehmer (event_id,user_id,status) VALUES (?,?,?)",
                                  eid, interaction.user.id, status)
        await interaction.response.edit_message(embed=await self.event_embed(row))

    async def _update_msg(self, row) -> None:
        g = self.bot.get_guild(row["guild_id"])
        ch = g.get_channel(row["channel_id"]) if g else None
        if not ch or not row["message_id"]:
            return
        try:
            msg = await ch.fetch_message(row["message_id"])
            await msg.edit(embed=await self.event_embed(row), view=None if not row["aktiv"] else event_view(row["id"]))
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------ /event
    @stufe("event")
    @event.command(name="erstellen", description="Erstellt ein Event/Einsatz/Übung mit Zu- und Absage")
    @app_commands.describe(zeitpunkt="z. B. 24.12.2026 18:00 oder nur 18:00 (heute)", ping="Rolle pingen")
    @app_commands.choices(art=[app_commands.Choice(name=f"{e} {a}", value=a) for a, e in arten().items()])
    async def erstellen(self, interaction: discord.Interaction, art: str, titel: app_commands.Range[str, 1, 200],
                        zeitpunkt: str, beschreibung: str | None = None, ort: str | None = None,
                        ping: discord.Role | None = None, kanal: discord.TextChannel | None = None) -> None:
        d = u.parse_datum(zeitpunkt)
        if not d:
            return await interaction.response.send_message(embed=u.fehler(T("allgemein.datum_beispiel", "Ungültiges Datum, z. B. `24.12.2026 18:00`.")),
                                                           ephemeral=True)
        await self.erstelle(interaction, art, titel, beschreibung, ort, int(d.timestamp()), ping, kanal)

    @stufe("event")
    @event.command(name="absagen", description="Sagt ein Event ab")
    async def absagen(self, interaction: discord.Interaction, nummer: int, grund: str | None = None) -> None:
        row = await self.bot.db.fetchone("SELECT * FROM events WHERE id=? AND guild_id=?", nummer, interaction.guild_id)
        if not row:
            return await interaction.response.send_message(embed=u.fehler(T("events.nicht_gefunden", "Event nicht gefunden.")), ephemeral=True)
        await self.bot.db.execute("UPDATE events SET aktiv=0 WHERE id=?", nummer)
        row = await self.bot.db.fetchone("SELECT * FROM events WHERE id=?", nummer)
        await self._update_msg(row)
        teil = await self.bot.db.fetchall("SELECT user_id FROM event_teilnehmer WHERE event_id=? AND status!='nein'", nummer)
        ch = interaction.guild.get_channel(row["channel_id"])
        if ch and teil:
            await ch.send(" ".join(f"<@{t['user_id']}>" for t in teil)[:1900],
                          embed=u.embed(T("events.abgesagt_titel", "❌ {art} abgesagt: {titel}", art=row['art'], titel=row['titel']), grund, u.ROT))
        await interaction.response.send_message(embed=u.ok(T("events.abgesagt_ok", "Event #{nummer} abgesagt.", nummer=nummer)), ephemeral=True)

    @stufe("jeder")
    @event.command(name="liste", description="Kommende Events")
    async def liste(self, interaction: discord.Interaction) -> None:
        rows = await self.bot.db.fetchall("SELECT * FROM events WHERE guild_id=? AND aktiv=1 AND zeitpunkt>? ORDER BY zeitpunkt LIMIT 15",
                                          interaction.guild_id, u.now() - 3600)
        zeilen = [f"`#{r['id']}` {arten().get(r['art'], '📅')} **{r['titel']}** – {u.ts(r['zeitpunkt'], 'f')}" for r in rows]
        await interaction.response.send_message(embed=u.embed(T("events.liste_titel", "📅 Kommende Events"), "\n".join(zeilen) or T("allgemein.keine", "Keine.")),
                                                ephemeral=True)

    # ----------------------------------------------------------- /appell
    @stufe("event")
    @appell.command(name="starten", description="Startet einen Appell mit Anwesend-Button")
    @app_commands.describe(dauer="Wie lange man sich melden kann, z. B. 10m", rolle="Wer muss anwesend sein?")
    async def appell_starten(self, interaction: discord.Interaction, dauer: str = "10m",
                             rolle: discord.Role | None = None, titel: str | None = None) -> None:
        sek = u.parse_dauer(dauer) or 600
        titel = titel or T("appell.standard_titel", "Morgenappell")
        ende = u.now() + sek
        aid = await self.bot.db.execute(
            "INSERT INTO appelle (guild_id,channel_id,titel,rolle_id,ende,ersteller) VALUES (?,?,?,?,?,?)",
            interaction.guild_id, interaction.channel_id, titel, rolle.id if rolle else None, ende, interaction.user.id)
        e = u.embed(T("appell.titel", "🫡 {titel}", titel=titel), T(
            "appell.text", "Alle {wer} antreten!\nMeldet euch bis {uhrzeit} ({restzeit}) als anwesend.",
            wer=rolle.mention if rolle else "Soldaten", uhrzeit=u.ts(ende, 'T'), restzeit=u.ts(ende, 'R')))
        v = discord.ui.View(timeout=None)
        v.add_item(AppellButton(aid))
        await interaction.response.send_message(content=P("appell", interaction.guild, rolle), embed=e, view=v,
                                                allowed_mentions=discord.AllowedMentions(roles=True, everyone=True))
        msg = await interaction.original_response()
        await self.bot.db.execute("UPDATE appelle SET message_id=? WHERE id=?", msg.id, aid)

    @stufe("event")
    @appell.command(name="beenden", description="Beendet den letzten (oder einen bestimmten) Appell sofort")
    async def appell_beenden(self, interaction: discord.Interaction, nummer: int | None = None) -> None:
        row = await self.bot.db.fetchone(
            "SELECT * FROM appelle WHERE guild_id=? AND aktiv=1 " + ("AND id=?" if nummer else "ORDER BY id DESC"),
            *((interaction.guild_id, nummer) if nummer else (interaction.guild_id,)))
        if not row:
            return await interaction.response.send_message(embed=u.fehler(T("appell.keiner", "Kein laufender Appell.")), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await self._appell_abschliessen(row)
        await interaction.followup.send(embed=u.ok(T("appell.beendet_ok", "Appell beendet.")), ephemeral=True)

    async def _appell_abschliessen(self, row) -> None:
        await self.bot.db.execute("UPDATE appelle SET aktiv=0 WHERE id=?", row["id"])
        g = self.bot.get_guild(row["guild_id"])
        ch = g.get_channel(row["channel_id"]) if g else None
        if not ch:
            return
        da = {r["user_id"] for r in await self.bot.db.fetchall("SELECT user_id FROM appell_anwesend WHERE appell_id=?", row["id"])}
        e = u.embed(T("appell.ergebnis", "📋 Ergebnis: {titel}", titel=row['titel']))
        e.add_field(name=T("appell.anwesend", "✅ Anwesend ({anzahl})", anzahl=len(da)), value=("\n".join(f"<@{x}>" for x in da)[:1024]) or "–")
        rolle = g.get_role(row["rolle_id"]) if row["rolle_id"] else None
        if rolle:
            abm = {r["user_id"] for r in await self.bot.db.fetchall(
                "SELECT user_id FROM abmeldungen WHERE guild_id=? AND aktiv=1 AND von<=?", g.id, u.now())}
            soll = {m.id for m in rolle.members if not m.bot}
            entschuldigt = (soll - da) & abm
            fehlt = soll - da - abm
            e.add_field(name=T("appell.entschuldigt", "📅 Entschuldigt ({anzahl})", anzahl=len(entschuldigt)),
                        value=("\n".join(f"<@{x}>" for x in entschuldigt)[:1024]) or "–")
            e.add_field(name=T("appell.unentschuldigt", "❌ Unentschuldigt ({anzahl})", anzahl=len(fehlt)), value=("\n".join(f"<@{x}>" for x in fehlt)[:1024]) or "–")
        try:
            if row["message_id"]:
                msg = await ch.fetch_message(row["message_id"])
                await msg.edit(view=None)
            await ch.send(embed=e)
        except discord.HTTPException:
            pass

    # --------------------------------------------------------- Ticker
    @tasks.loop(minutes=1)
    async def ticker(self) -> None:
        jetzt = u.now()
        minuten = int(self.bot.cfg.get("events", {}).get("erinnerung_minuten", 15))
        rows = await self.bot.db.fetchall("SELECT * FROM events WHERE aktiv=1 AND erinnert=0 AND zeitpunkt<=?",
                                          jetzt + minuten * 60)
        for r in rows:
            await self.bot.db.execute("UPDATE events SET erinnert=1 WHERE id=?", r["id"])
            if r["zeitpunkt"] < jetzt - 3600:
                continue
            g = self.bot.get_guild(r["guild_id"])
            ch = g.get_channel(r["channel_id"]) if g else None
            teil = await self.bot.db.fetchall("SELECT user_id FROM event_teilnehmer WHERE event_id=? AND status IN ('ja','vl')",
                                              r["id"])
            if ch and teil:
                try:
                    await ch.send(" ".join(f"<@{t['user_id']}>" for t in teil)[:1900], embed=u.embed(
                        T("events.erinnerung_titel", "⏰ Erinnerung: {titel}", titel=r['titel']),
                        T("events.erinnerung_text", "Beginnt {zeit}!", zeit=u.ts(r['zeitpunkt'], 'R')) +
                        (f"\n📍 {r['ort']}" if r["ort"] else "")))
                except discord.HTTPException:
                    pass
        # Events 3h nach Beginn automatisch beenden
        alte = await self.bot.db.fetchall("SELECT * FROM events WHERE aktiv=1 AND zeitpunkt<?", jetzt - 3 * 3600)
        for r in alte:
            await self.bot.db.execute("UPDATE events SET aktiv=0 WHERE id=?", r["id"])
            await self._update_msg(await self.bot.db.fetchone("SELECT * FROM events WHERE id=?", r["id"]))
        for r in await self.bot.db.fetchall("SELECT * FROM appelle WHERE aktiv=1 AND ende<=?", jetzt):
            await self._appell_abschliessen(r)

    @ticker.before_loop
    async def _warten(self) -> None:
        await self.bot.wait_until_ready()


# ==========================================================================
#  MODUL: ALLGEMEIN – Hilfe, Infos, Umfragen, Embeds
#  Allgemeine Befehle: /hilfe, /ping, /serverinfo, /userinfo, /avatar, /umfrage, /embed, /ankuendigung
# ==========================================================================

ZAHLEN = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class EmbedModal(discord.ui.Modal, title="Embed"):
    def __init__(self, kanal: discord.abc.Messageable, ping: discord.Role | None, ankuendigung: bool) -> None:
        super().__init__(title=T("allgemein.modal_ankuendigung", "Ankündigung erstellen") if ankuendigung
                         else T("allgemein.modal_embed", "Embed erstellen"))
        self.kanal, self.ping, self.ankuendigung = kanal, ping, ankuendigung
        self.titel = discord.ui.TextInput(label=T("allgemein.feld_titel", "Titel"), required=False, max_length=256)
        self.text = discord.ui.TextInput(label=T("allgemein.feld_text", "Text"), style=discord.TextStyle.paragraph,
                                         max_length=4000)
        self.farbe = discord.ui.TextInput(label=T("allgemein.feld_farbe", "Farbe (Hex, z. B. #4E5B31)"),
                                          required=False, max_length=7)
        self.bild = discord.ui.TextInput(label=T("allgemein.feld_bild", "Bild-URL (optional)"), required=False)
        self.fusszeile = discord.ui.TextInput(label=T("allgemein.feld_fusszeile", "Fußzeile (optional)"),
                                              required=False, max_length=200)
        for f in (self.titel, self.text, self.farbe, self.bild, self.fusszeile):
            self.add_item(f)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            farbe = discord.Color.from_str(self.farbe.value) if self.farbe.value else u.FARBE
        except ValueError:
            farbe = u.FARBE
        titel = self.titel.value or None
        if self.ankuendigung and titel:
            titel = f"{T('symbole.ankuendigung', '📢')} {titel}"
        e = u.embed(titel, self.text.value, farbe)
        if self.bild.value:
            e.set_image(url=self.bild.value)
        if self.fusszeile.value:
            e.set_footer(text=self.fusszeile.value)
        if self.ankuendigung:
            e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        try:
            ping = P("ankuendigung", interaction.guild, self.ping) if self.ankuendigung else None
            await self.kanal.send(content=ping, embed=e,
                                  allowed_mentions=discord.AllowedMentions(roles=True, everyone=True))
        except discord.HTTPException as ex:
            return await interaction.response.send_message(embed=u.fehler(T("allgemein.senden_fehler", "Senden fehlgeschlagen: {fehler}", fehler=ex)), ephemeral=True)
        await interaction.response.send_message(embed=u.ok(T("allgemein.gesendet", "Gesendet.")), ephemeral=True)


class Allgemein(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.start = time.time()

    @stufe("jeder")
    @app_commands.command(name="hilfe", description="Zeigt alle Befehle, die du nutzen darfst")
    @app_commands.guild_only()
    async def hilfe(self, interaction: discord.Interaction) -> None:
        mgr = self.bot.cmd_manager
        guild = discord.Object(id=interaction.guild_id)
        cmds = self.bot.tree.get_commands(guild=guild, type=discord.AppCommandType.chat_input) or \
            self.bot.tree.get_commands(type=discord.AppCommandType.chat_input)
        bereiche: list[tuple[str, list[str]]] = []
        einzel: list[str] = []
        for c in cmds:
            if isinstance(c, app_commands.Group):
                zeilen = [f"`/{s.qualified_name}` – {s.description}" for s in c.walk_commands()
                          if isinstance(s, app_commands.Command) and mgr.erlaubt(interaction.user, s)[0]]
                if zeilen:
                    bereiche.append((f"{T('symbole.ordner', '📁')} /{c.name} – {c.description}", zeilen))
            elif mgr.erlaubt(interaction.user, c)[0]:
                einzel.append(f"`/{c.name}` – {c.description}")
        e = u.embed(T("hilfe.titel", "📖 Hilfe"), T("hilfe.text", "Alle Befehle, die **du** nutzen darfst:"))
        if einzel:
            bereiche.insert(0, (T("hilfe.allgemein", "⭐ Allgemein"), einzel))
        embeds = [e]
        for titel, zeilen in bereiche:
            text = "\n".join(zeilen)
            if len(embeds[-1]) + len(text) > 5500 or len(embeds[-1].fields) >= 24:
                embeds.append(u.embed(None))
            for i, teil in enumerate(u.chunk_lines(zeilen, 1000)):
                embeds[-1].add_field(name=titel if i == 0 else f"{titel} (Forts.)", value=teil, inline=False)
        await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)

    @stufe("jeder")
    @app_commands.command(name="ping", description="Zeigt die Bot-Latenz")
    async def ping(self, interaction: discord.Interaction) -> None:
        up = u.fmt_dauer(time.time() - self.start)
        await interaction.response.send_message(
            embed=u.embed(T("ping.titel", "🏓 Pong"), T("ping.text", "Latenz: **{ms} ms**\nOnline seit: **{online}**",
                                                      ms=round(self.bot.latency * 1000), online=up)), ephemeral=True)

    @stufe("jeder")
    @app_commands.command(name="serverinfo", description="Infos über den Server")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        g = interaction.guild
        soldaten = (await self.bot.db.fetchone("SELECT COUNT(*) c FROM soldaten WHERE guild_id=? AND status='aktiv'", g.id))["c"]
        im_dienst = (await self.bot.db.fetchone("SELECT COUNT(*) c FROM dienst WHERE guild_id=? AND ende IS NULL", g.id))["c"]
        e = u.embed(T("serverinfo.titel", "🏰 {server}", server=g.name), g.description)
        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        e.add_field(name=T("serverinfo.mitglieder", "Mitglieder"), value=str(g.member_count))
        e.add_field(name=T("serverinfo.soldaten", "Aktive Soldaten"), value=str(soldaten))
        e.add_field(name=T("serverinfo.im_dienst", "Im Dienst"), value=str(im_dienst))
        e.add_field(name=T("serverinfo.rollen", "Rollen"), value=str(len(g.roles)))
        e.add_field(name=T("serverinfo.kanaele", "Kanäle"), value=str(len(g.channels)))
        e.add_field(name=T("serverinfo.boosts", "Boosts"), value=str(g.premium_subscription_count))
        e.add_field(name=T("serverinfo.inhaber", "Inhaber"), value=f"<@{g.owner_id}>")
        e.add_field(name=T("serverinfo.erstellt", "Erstellt"), value=u.ts(g.created_at.timestamp(), "D"))
        await interaction.response.send_message(embed=e)

    @stufe("jeder")
    @app_commands.command(name="userinfo", description="Infos über eine Person")
    @app_commands.guild_only()
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        m = user or interaction.user
        e = u.embed(T("userinfo.titel", "👤 {name}", name=m.display_name), f"{m.mention} · `{m}` · {m.id}")
        e.set_thumbnail(url=m.display_avatar.url)
        e.add_field(name=T("userinfo.erstellt", "Account erstellt"), value=u.ts(m.created_at.timestamp(), "D"))
        e.add_field(name=T("userinfo.beigetreten", "Beigetreten"), value=u.ts(m.joined_at.timestamp(), "D") if m.joined_at else "–")
        einh = self.bot.rechte.einheiten_von(m)
        if einh:
            e.add_field(name=T("userinfo.einheiten", "Einheiten"), value="\n".join(f"{x.emoji} {x.name} – {x.positionen[p].titel}" for x, p in einh),
                        inline=False)
        rollen = [r.mention for r in reversed(m.roles) if r != interaction.guild.default_role]
        e.add_field(name=T("userinfo.rollen", "Rollen ({anzahl})", anzahl=len(rollen)), value=" ".join(rollen)[:1024] or "–", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @stufe("jeder")
    @app_commands.command(name="avatar", description="Zeigt das Profilbild einer Person")
    async def avatar(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        m = user or interaction.user
        e = u.embed(T("avatar.titel", "🖼️ {name}", name=m.display_name))
        e.set_image(url=m.display_avatar.with_size(1024).url)
        await interaction.response.send_message(embed=e)

    @stufe("support")
    @app_commands.command(name="umfrage", description="Startet eine Umfrage (Optionen mit ; trennen)")
    @app_commands.describe(optionen="z. B. Ja;Nein;Vielleicht – leer lassen für 👍/👎")
    @app_commands.guild_only()
    async def umfrage(self, interaction: discord.Interaction, frage: app_commands.Range[str, 1, 250],
                      optionen: str | None = None, ping: discord.Role | None = None) -> None:
        opts = [o.strip() for o in (optionen or "").split(";") if o.strip()][:10]
        e = u.embed(T("umfrage.titel", "📊 {frage}", frage=frage))
        e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        if opts:
            e.description = "\n".join(f"{ZAHLEN[i]} {o}" for i, o in enumerate(opts))
        await interaction.response.send_message(content=P("umfrage", interaction.guild, ping), embed=e,
                                                allowed_mentions=discord.AllowedMentions(roles=True, everyone=True))
        msg = await interaction.original_response()
        for emoji in (ZAHLEN[:len(opts)] if opts else [T("umfrage.emoji_ja", "👍"), T("umfrage.emoji_nein", "👎")]):
            await msg.add_reaction(emoji)

    @stufe("admin")
    @app_commands.command(name="embed", description="Erstellt ein eigenes Embed in einem Kanal")
    @app_commands.guild_only()
    async def embed_cmd(self, interaction: discord.Interaction, kanal: discord.TextChannel | None = None) -> None:
        await interaction.response.send_modal(EmbedModal(kanal or interaction.channel, None, False))

    @stufe("admin")
    @app_commands.command(name="ankuendigung", description="Erstellt eine Ankündigung")
    @app_commands.guild_only()
    async def ankuendigung(self, interaction: discord.Interaction, kanal: discord.TextChannel,
                           ping: discord.Role | None = None) -> None:
        await interaction.response.send_modal(EmbedModal(kanal, ping, True))

    @stufe("admin")
    @app_commands.command(name="sagen", description="Lässt den Bot eine Nachricht schreiben")
    @app_commands.guild_only()
    async def sagen(self, interaction: discord.Interaction, text: str, kanal: discord.TextChannel | None = None) -> None:
        await (kanal or interaction.channel).send(text.replace("\\n", "\n"))
        await interaction.response.send_message(embed=u.ok(T("allgemein.gesendet", "Gesendet.")), ephemeral=True)


# ==========================================================================
#  MODUL: LOGS – Willkommen, Autorolle, Nachrichten-Logs
#  Willkommen/Abschied, Autorolle und Nachrichten-Logs
# ==========================================================================

class u_leer(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class Logs(commands.Cog):
    willkommen = app_commands.Group(name="willkommen", description="Willkommensnachricht für neue Mitglieder",
                                    guild_only=True)

    def __init__(self, bot) -> None:
        self.bot = bot

    async def willkommen_embed(self, member: discord.Member) -> discord.Embed:
        """Baut die Willkommensnachricht. Mit /willkommen setup gespeicherte Werte gehen vor den Standardtexten."""
        gid = member.guild.id
        conf = self.bot.cfg.get("willkommen", {})
        titel = await self.bot.db.get_setting(gid, "willkommen_titel")
        text = await self.bot.db.get_setting(gid, "willkommen_text")
        bild = await self.bot.db.get_setting(gid, "willkommen_bild") or conf.get("bild")
        v = self._vars(member)
        if titel:
            titel = titel.replace("\\n", "\n").format_map(u_leer(v))
        else:
            titel = T("willkommen.titel", "🇩🇪 Willkommen in der Bundeswehrkaserne !", **v)
        if text:
            text = text.replace("\\n", "\n").format_map(u_leer(v))
        else:
            text = T("willkommen.text", "Moin {user}! Schön, dass du da bist.\n"
                     "Bei uns stehen **Disziplin, Respekt und Kameradschaft** an erster Stelle.\n"
                     "Lies dir die Regeln durch und bewirb dich im Karriere Center.\n"
                     "Du bist Mitglied Nr. **{mitglieder}**.", **v)
        e = u.embed(titel, text)
        e.set_thumbnail(url=member.display_avatar.url)
        if bild:
            e.set_image(url=bild)
        return e

    # ------------------------------------------------------- /willkommen
    @stufe("admin")
    @willkommen.command(name="setup", description="Legt Kanal und Text der Willkommensnachricht fest")
    @app_commands.describe(kanal="Hier erscheint die Willkommensnachricht, wenn jemand dem Server beitritt",
                           titel="Eigener Titel (optional)",
                           text="Eigener Text, \\n = neue Zeile. Platzhalter: {user} {user_name} {server} {mitglieder}",
                           bild="Bild-URL unter der Nachricht (optional)")
    async def willkommen_setup(self, interaction: discord.Interaction, kanal: discord.TextChannel,
                               titel: app_commands.Range[str, 1, 256] | None = None,
                               text: app_commands.Range[str, 1, 3500] | None = None,
                               bild: str | None = None) -> None:
        gid = interaction.guild_id
        await self.bot.db.set_setting(gid, "kanal_willkommen", kanal.id)
        if titel:
            await self.bot.db.set_setting(gid, "willkommen_titel", titel)
        if text:
            await self.bot.db.set_setting(gid, "willkommen_text", text)
        if bild:
            await self.bot.db.set_setting(gid, "willkommen_bild", bild)
        await interaction.response.send_message(
            embed=u.ok(T("willkommen.setup_ok", "Willkommensnachrichten erscheinen jetzt in {kanal}.\n"
                         "Mit `/willkommen test` siehst du eine Vorschau.", kanal=kanal.mention)), ephemeral=True)

    @stufe("admin")
    @willkommen.command(name="test", description="Zeigt dir eine Vorschau der Willkommensnachricht")
    async def willkommen_test(self, interaction: discord.Interaction) -> None:
        e = await self.willkommen_embed(interaction.user)
        await interaction.response.send_message(content=T("willkommen.vorschau", "**Vorschau:**"), embed=e,
                                                ephemeral=True)

    @stufe("admin")
    @willkommen.command(name="zuruecksetzen", description="Setzt Titel, Text und Bild auf den Standard zurück")
    async def willkommen_reset(self, interaction: discord.Interaction) -> None:
        for k in ("willkommen_titel", "willkommen_text", "willkommen_bild"):
            await self.bot.db.set_setting(interaction.guild_id, k, None)
        await interaction.response.send_message(
            embed=u.ok(T("willkommen.reset_ok", "Standard-Willkommensnachricht wiederhergestellt.")), ephemeral=True)

    @staticmethod
    def _vars(member: discord.Member) -> dict:
        return dict(user=member.mention, user_name=member.display_name, server=member.guild.name,
                    mitglieder=member.guild.member_count)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        conf = self.bot.cfg.get("willkommen", {})
        rollen = [r for n in conf.get("autorollen", []) if (r := self.bot.rechte.rolle(member.guild, n))]
        if rollen and not member.bot:
            try:
                await member.add_roles(*rollen, reason="Autorolle")
            except discord.Forbidden:
                pass
        cid = await self.bot.db.get_setting(member.guild.id, "kanal_willkommen")
        if cid and (ch := member.guild.get_channel(int(cid))):
            e = await self.willkommen_embed(member)
            try:
                await ch.send(content=P("willkommen", member.guild, member), embed=e,
                              allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True))
            except discord.HTTPException:
                pass
        if conf.get("dm"):
            await u.dm(member, u.embed(T("willkommen.dm_titel", "Willkommen auf {server}", **self._vars(member)),
                                     T("willkommen.dm_text", "Willkommen auf {server}! Bewirb dich im Karriere Center, um loszulegen.",
                                       **self._vars(member))))
        e = u.embed(T("logs.beitritt", "📥 Beitritt"), f"{member.mention} (`{member}`)\n"
                    + T("logs.account_erstellt", "Account erstellt {zeit}", zeit=u.ts(member.created_at.timestamp(), 'R')), u.GRUEN)
        await u.send_log(self.bot, member.guild, "nachrichten", e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        cid = await self.bot.db.get_setting(member.guild.id, "kanal_abschied")
        if cid and (ch := member.guild.get_channel(int(cid))):
            try:
                await ch.send(embed=u.embed(T("willkommen.abschied_titel", "👋 Auf Wiedersehen"),
                                             T("willkommen.abschied", "**{user_name}** hat die Kaserne verlassen.",
                                               **self._vars(member)), u.GELB))
            except discord.HTTPException:
                pass
        # Laufenden Dienst beenden
        await self.bot.db.execute("UPDATE dienst SET ende=? WHERE guild_id=? AND user_id=? AND ende IS NULL",
                                  u.now(), member.guild.id, member.id)
        e = u.embed(T("logs.verlassen", "📤 Verlassen"), f"`{member}` ({member.id})", u.ROT)
        await u.send_log(self.bot, member.guild, "nachrichten", e)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        e = u.embed(T("logs.geloescht", "🗑️ Nachricht gelöscht"), T("logs.von_in", "Von {user} in {kanal}",
                    user=message.author.mention, kanal=message.channel.mention), u.ROT)
        e.add_field(name=T("logs.inhalt", "Inhalt"), value=(message.content or "*(kein Text)*")[:1024], inline=False)
        if message.attachments:
            e.add_field(name=T("logs.anhaenge", "Anhänge"), value="\n".join(a.filename for a in message.attachments)[:1024])
        await u.send_log(self.bot, message.guild, "nachrichten", e)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not before.guild or before.author.bot or before.content == after.content:
            return
        e = u.embed(T("logs.bearbeitet", "✏️ Nachricht bearbeitet"), f"Von {before.author.mention} in {before.channel.mention} · "
                    f"[Zur Nachricht]({after.jump_url})", u.GELB)
        e.add_field(name=T("logs.vorher", "Vorher"), value=(before.content or "–")[:1024], inline=False)
        e.add_field(name=T("logs.nachher", "Nachher"), value=(after.content or "–")[:1024], inline=False)
        await u.send_log(self.bot, before.guild, "nachrichten", e)


MODULE = [Setup, Personal, Karriere, Dienst, Moderation, Tickets, Events, Allgemein, Logs]


# ==========================================================================
#  START
# ==========================================================================

def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        sys.exit("DISCORD_TOKEN fehlt! Lege eine .env-Datei an (siehe .env.example).")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    )
    bot = BwBot()
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
