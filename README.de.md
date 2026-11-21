<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/readme/assets/studio-logo-dark.png">
    <img src="docs/readme/assets/studio-logo-light.png" alt="Skillto.ai | 个人工作台" width="650">
  </picture>
</p>

<h1 align="center">Skillto.ai Studio</h1>

<p align="center">Der KI-native persönliche Arbeitsplatz für Agenten</p>

<p align="center"><a href="#übersicht">Übersicht</a> · <a href="#architektur">Architektur</a> · <a href="#funktionen">Funktionen</a> · <a href="#screenshots">Screenshots</a> · <a href="#schnellstart">Schnellstart</a> · <a href="skills/skillto-ai-studio/references/installation.md">Dokumentation</a><br>
  <a href="https://www.skillto.ai/">Skillto.ai</a> ·
  <a href="https://github.com/skilltoAI/skillto-ai-studio">GitHub</a> ·
  <a href="skills/skillto-ai-studio/SKILL.md"><kbd>20 Skills</kbd></a> ·
  <a href="apps/stass/README.md"><kbd>STASS MCP</kbd></a>
</p>

<p align="center"><a href="README.zh-CN.md"><kbd>简体中文</kbd></a> &nbsp; <a href="README.md"><kbd>English</kbd></a> &nbsp; <a href="README.ja.md"><kbd>日本語</kbd></a> &nbsp; <kbd>Deutsch</kbd></p>

## Übersicht

**Skillto.ai Studio ist ein KI-nativer persönlicher Arbeitsplatz.** Beschreibe dein Ziel in natürlicher Sprache. Der Agent wählt passende Skills aus, arbeitet per MCP mit deinen Einträgen und hinterlegt prüfbare Ergebnisse in Wissenssammlungen, Tabellen, Skripten und Storyboards. Du kannst die Ergebnisse jederzeit prüfen und bearbeiten.

Studio verbindet deinen Arbeitsplatz mit dem offiziellen Angebot von Skillto.ai. Verfügbare **KI-Assets, KI-APIs und Skills** von der Website lassen sich nach Einrichtung und Autorisierung der Dienste in deine Workflows einbinden. Recherchematerial, Zwischenschritte und Ergebnisse bleiben von der Idee über die Generierung und den Schnitt bis zur Freigabe im selben Projekt. [Skillto.ai besuchen](https://www.skillto.ai/)

## KI-Assets für visuelle Gestaltung

Die Rot-Weiß-Modellbibliothek zeigt Bewegungsvorlagen und die zugehörigen Prompts auf derselben Karte. Durchsuche offizielle Themen oder lokale Sammlungen, spiele Referenzclips ab und kopiere Prompts für deine eigenen Projekte. Der Screenshot zeigt ein kostenloses offizielles Thema im Workspace.

![Rot-Weiß-Modellbibliothek mit Themen, Bewegungsvorlagen und kopierbaren Prompts](docs/readme/assets/studio-red-white-model-library.png)

## Architektur

![Architektur von Skillto.ai Studio. Agenten arbeiten mit Skills und Personal MCP auf dem lokalen Personal Server und greifen separat auf Skillto.ai zu.](docs/readme/assets/studio-architecture.svg)

Agenten wählen Workflows über Skills und arbeiten per Personal MCP im lokalen Arbeitsbereich. Der Personal Server speichert Projektdaten. Autorisierte Clients nutzen Cloud-Assets und Generierung über Skillto.ai.

## Für wen ist das Projekt gedacht?

- **KI-Dozierende und Anbieter kostenpflichtiger Inhalte** können Themen recherchieren, Referenzvideos analysieren, Kursskripte schreiben und Cover sowie Storyboards prüfen.
- **KI-Anwender im Büroalltag** können Materialien, Dokumente und Aufgaben in Wissenssammlungen, Tabellen und Berichten organisieren und Anmerkungen festhalten.
- **KI-Kreative** können Figuren, Bildreferenzen, Einstellungen und Motion-Vorlagen verwalten sowie Bildgenerierung, Videogenerierung und Schnitt koordinieren.

## Funktionen

- **Skill-Orchestrierung.** Ein zentraler Skill leitet Aufgaben an 19 spezialisierte Skills für Recherche, Medienanalyse, Büroarbeit, Storyboards, Cover und Berichte weiter.
- **Ein gemeinsamer Arbeitsplatz für Menschen und Agenten.** Unterstützte Agenten lesen und aktualisieren Einträge über STASS MCP. Menschen prüfen und bearbeiten dieselben Einträge im Browser.
- **KI-gestützter Schnitt und Motion Design.** Analysiere Referenzclips, wähle Ausschnitte aus und plane den Schnitt anhand von Rohmaterial und Untertiteln mit HyperFrames oder Remotion. Motion verwaltet Vorlagen und Vorschauen.
- **KI-Bild- und Videogenerierung.** Entwickle aus Cover-Ideen, Figurenreferenzen und Einstellungen visuelle Workflows. Creator MCP ordnet Medien zu, prüft Abläufe, führt autorisierte Generierungsaufträge aus und ruft Ergebnisse ab. Verfügbare APIs, Modelle und Skills richten sich nach dem Angebot der Website und den Kontoberechtigungen.

[Skill-Verzeichnis](README.md#skill-catalogue) · [Kompatibilität und Abhängigkeiten](skills/skillto-ai-studio/references/compatibility.md)

## Screenshots

Die ersten beiden Bilder zeigen den Windows-Launcher und den Beam-Editor aus dem Integrationsbuild. Der Standardbranch enthält diesen Build noch nicht. Ein Windows-Installer steht noch nicht zum Download bereit.

### Desktop-Arbeitsplatz

Der Windows-Launcher zeigt den Status des persönlichen Servers und bietet Schaltflächen zum Starten, Beenden und Öffnen des Arbeitsplatzes. Auch Browserprofile, Web-Kopplungscodes und die 3D-Bildschirmaufnahme sind von dort erreichbar. Im Browser stehen Multimedia-Tabellen, Tags, Motion-Vorlagen, Skripte und Storyboards bereit.

![Desktop-Arbeitsplatz](docs/readme/assets/studio-desktop-workspace.png)

### 3D-Bildschirmaufnahme und Schnitt

Der Eintrag **3D-Bildschirmaufnahme** öffnet den separaten Beam-Editor für Produktdemos und Tutorials. Auf der Zeitleiste lassen sich Clips schneiden und mit 2D-Zoom, 3D-Kamerafahrten oder einer Lupe bearbeiten. Fokus per Mauszeiger oder manuell, Perspektivvorgaben, Untertitel und Ton lassen sich anpassen. Der Editor startet auch bei ausgeschaltetem STASS-Dienst.

![3D-Bildschirmaufnahme und Schnitt](docs/readme/assets/studio-3d-recording.png)

Die folgenden Aufnahmen zeigen einen laufenden STASS-Arbeitsplatz mit fiktiven Beispieldaten.

**Motion-Vorlagen mit Cover-Vorschau**

![Motion-Vorlagen mit Cover-Vorschau](docs/readme/assets/studio-motion-gallery.png)

**Multimedia-Tabelle mit Bildvorschau**

![Multimedia-Tabelle mit Bildvorschau](docs/readme/assets/studio-media-table.png)

**Redaktionsplanung mit Prüfanmerkungen**

![Redaktionsplanung mit Prüfanmerkungen](docs/readme/assets/studio-tables.png)

**Skriptversionen und zeilenweise Anmerkungen**

![Skriptversionen und zeilenweise Anmerkungen](docs/readme/assets/studio-rewrite.png)

**Verknüpftes Motion-Storyboard im Skriptbereich**

![Verknüpftes Motion-Storyboard im Skriptbereich](docs/readme/assets/studio-storyboard.png)

## Schnellstart

Benötigt werden Git, Python ab Version 3.10 und der gewünschte Client. Die folgenden Befehle zeigen die vorgesehenen Änderungen an und installieren die Skills:

```sh
git clone https://github.com/skilltoAI/skillto-ai-studio.git
cd skillto-ai-studio
python scripts/install.py --agent codex --groups
```

Für Claude Code ersetzt du `--agent codex` durch `--agent claude`. In einer neuen Sitzung startest du den Skill mit `$skillto-ai-studio` in Codex oder `/skillto-ai-studio` in Claude Code.

Die Befehle installieren die Skills. Die Windows-Anwendung, die MCP-Registrierung und externe Generierungsdienste werden separat eingerichtet. Unter [GitHub Releases](https://github.com/skilltoAI/skillto-ai-studio/releases) steht derzeit kein Windows-Installer bereit. Ein Offline-Testpaket lässt sich aus dem GitHub-Quellcode nach der unten verlinkten Windows-Anleitung erstellen. Die vollständige Prüfung auf anderen Windows-Rechnern steht noch aus.

[Windows-Installation und Status](README.md#windows-workspace) · [Installation, Updates und Fehlerbehebung](skills/skillto-ai-studio/references/installation.md) · [Mitwirken](CONTRIBUTING.md)
