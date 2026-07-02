# Bande Rythmo Local Studio - Conception Produit et Technique

## 1. Vision

Bande Rythmo Local Studio est une application professionnelle, entierement locale, destinee aux studios de doublage, auteurs-adaptateurs, directeurs artistiques, laboratoires de localisation et createurs independants.

Objectif : importer une video, extraire automatiquement la parole, produire une transcription alignee mot par mot, generer une bande rythmo lisible, permettre la correction humaine, lire la video et la bande de maniere synchronisee, puis exporter les livrables professionnels.

Contraintes principales :

- execution locale sur `localhost:8000` ;
- backend Python ;
- aucune dependance a une API cloud ;
- IA locale uniquement via `llama.cpp` si necessaire ;
- architecture extensible pour differents moteurs ASR, formats d'export et workflows metier ;
- performance acceptable sur CPU, acceleree sur GPU si disponible ;
- produit commercialisable, maintenable et distribuable.

## 2. Choix Techniques

### Backend

- Python 3.11 ou 3.12
- FastAPI pour l'API REST et WebSocket
- Uvicorn comme serveur local
- SQLite par defaut, avec SQLAlchemy
- Alembic pour les migrations
- Pydantic pour les schemas API
- Celery ou RQ optionnel, mais une queue interne Python suffit pour la V1 locale
- FFmpeg pour extraction audio, transcodage, rendus video et muxing
- OpenCV ou PyAV pour lecture metadata et frames
- NumPy pour calculs temporels et geometrie
- Pillow ou CairoSVG pour rendu image de la bande
- MoviePy ou pipeline FFmpeg direct pour l'export video final

### Reconnaissance Vocale et Alignement

Options locales recommandees :

- Whisper.cpp ou faster-whisper local pour transcription initiale
- Aeneas, Montreal Forced Aligner, WhisperX local ou alignement custom pour alignement mot par mot
- llama.cpp uniquement pour post-traitement linguistique local :
  - ponctuation ;
  - segmentation en repliques ;
  - normalisation ;
  - detection approximative de personnages ;
  - reformulation d'aide, jamais comme source temporelle principale.

### Frontend

- Vite + React + TypeScript
- Canvas 2D pour la bande rythmo interactive
- WebCodecs si disponible pour performances avancees, fallback video HTML5
- Zustand ou Redux Toolkit pour l'etat applicatif
- TanStack Query pour les appels API
- Tailwind ou CSS modules avec design system interne
- WebSocket pour progression des jobs et synchronisation temps reel

### Distribution

- Mode developpement : `python -m app.main`, serveur `localhost:8000`
- Mode desktop commercial : PyInstaller, Briefcase ou Tauri avec backend embarque
- FFmpeg et modeles locaux livres comme dependances optionnelles ou detectes au premier lancement

## 3. Architecture Generale

```text
Utilisateur
  |
  v
Frontend React
  | REST/WebSocket
  v
FastAPI localhost:8000
  |
  +-- Project Service
  +-- Media Service
  +-- Audio Service
  +-- ASR Service
  +-- Alignment Service
  +-- Rythmo Layout Engine
  +-- Export Service
  +-- Local AI Service llama.cpp
  |
  v
SQLite + Filesystem local
```

Principes :

- les gros fichiers restent sur disque ;
- la base stocke les metadonnees, segments, mots, versions et exports ;
- les traitements longs sont executes sous forme de jobs ;
- chaque etape du pipeline est rejouable ;
- les corrections utilisateur ne sont jamais ecrasees par une relance automatique.

## 4. Structure des Dossiers

```text
bande-rythmo/
  app/
    main.py
    config.py
    api/
      routes_projects.py
      routes_media.py
      routes_jobs.py
      routes_rythmo.py
      routes_exports.py
      websocket.py
    core/
      database.py
      paths.py
      logging.py
      security.py
      jobs.py
    models/
      project.py
      media.py
      transcript.py
      speaker.py
      rythmo.py
      export.py
    schemas/
      project.py
      media.py
      transcript.py
      rythmo.py
      export.py
    services/
      media_probe.py
      video_processing.py
      audio_extraction.py
      speech_recognition.py
      word_alignment.py
      speaker_detection.py
      local_llm.py
      rythmo_layout.py
      rythmo_renderer.py
      export_video.py
      export_subtitles.py
      export_xml_json.py
    workers/
      pipeline.py
      tasks.py
    storage/
      repository.py
  frontend/
    src/
      api/
      components/
      features/
        import/
        timeline/
        transcript/
        rythmo/
        export/
      stores/
      styles/
      main.tsx
  data/
    projects/
    models/
    temp/
    exports/
  tests/
    unit/
    integration/
    e2e/
  docs/
    CONCEPTION.md
```

## 5. Pipeline de Traitement

### Etape 1 - Import Video

Entree :

- MP4, MOV, MKV, AVI ;
- piste audio mono, stereo ou multicanal ;
- metadata detectee par FFprobe.

Actions :

1. copier ou referencer le fichier source ;
2. calculer hash du media ;
3. extraire duree, FPS, resolution, codecs ;
4. generer proxy video leger si necessaire ;
5. creer miniatures et waveform audio.

### Etape 2 - Extraction Audio

Sortie recommandee :

- WAV PCM mono ;
- 16 kHz pour ASR ;
- 48 kHz conserve pour exports professionnels.

Commande type :

```bash
ffmpeg -i input.mp4 -vn -ac 1 -ar 16000 audio_asr.wav
```

Optimisations :

- normalisation loudness optionnelle ;
- suppression bruit optionnelle ;
- VAD pour isoler zones parlees ;
- cache par hash media.

### Etape 3 - Reconnaissance Vocale

Sortie :

- segments avec timestamps approximatifs ;
- texte brut ;
- langue detectee ou imposee.

Schema :

```json
{
  "segments": [
    {
      "start": 12.42,
      "end": 15.80,
      "text": "Je ne voulais pas partir maintenant.",
      "confidence": 0.91
    }
  ]
}
```

### Etape 4 - Alignement Mot par Mot

Objectif : convertir les segments ASR en mots individuellement times.

Sortie :

```json
{
  "words": [
    {
      "text": "Je",
      "start": 12.42,
      "end": 12.58,
      "confidence": 0.88,
      "locked": false
    }
  ]
}
```

Strategie :

1. utiliser les timestamps mot par mot du moteur si disponibles ;
2. sinon, appliquer forced alignment local ;
3. fallback : repartition proportionnelle par longueur phonemique ou nombre de caracteres ;
4. marquer les mots incertains pour correction manuelle.

### Etape 5 - Segmentation Rythmo

La bande rythmo ne doit pas seulement afficher des sous-titres. Elle doit produire une lecture fluide adaptee au doublage.

Regles :

- regrouper les mots en repliques ;
- respecter respirations, silences et changements de locuteur ;
- eviter les blocs trop longs ;
- conserver les mots verrouilles par l'utilisateur ;
- calculer position horizontale selon le temps ;
- calculer position verticale par ligne, locuteur ou piste ;
- afficher les attaques, fins, pauses et changements de rythme.

Algorithme de layout :

```text
pixels_per_second = zoom * base_scale
x_start = (word.start - viewport_start) * pixels_per_second
x_end = (word.end - viewport_start) * pixels_per_second
width = max(min_word_width, x_end - x_start)
baseline_y = track_y + speaker_lane_offset
```

Gestion collisions :

- si deux mots se chevauchent visuellement, fusionner dans un groupe ;
- si une replique depasse la piste, passage sur ligne secondaire ;
- si zoom faible, afficher blocs de repliques au lieu des mots.

### Etape 6 - Edition Humaine

Fonctions indispensables :

- correction texte ;
- decalage mot, replique ou piste ;
- verrouillage d'un mot ou segment ;
- split/merge de repliques ;
- attribution locuteur/personnage ;
- ajout de commentaires ;
- historique undo/redo ;
- sauvegarde automatique ;
- versions de transcription.

### Etape 7 - Lecture Synchronisee

La video est la source de temps.

Boucle principale :

```text
video.currentTime -> store timeline -> canvas render -> playhead position
```

Exigences :

- drift inferieur a 20 ms en lecture normale ;
- zoom et scroll independants ;
- prechargement canvas ;
- rendu 60 fps vise, 30 fps minimum acceptable ;
- lecture image par image ;
- raccourcis clavier professionnels.

### Etape 8 - Export

Formats :

- JSON projet complet ;
- XML interne ou compatible outil tiers ;
- SRT ;
- WebVTT ;
- ASS/SSA ;
- EDL/CSV optionnel ;
- video avec bande rythmo incrustee ;
- sequence PNG de bande ;
- WAV audio extrait.

Export video :

1. rendre la bande rythmo en frames transparentes ;
2. composer avec video source ou proxy haute qualite ;
3. encoder H.264/H.265 ;
4. muxer audio original ;
5. generer rapport d'export.

## 6. API REST

Base URL : `http://localhost:8000/api`

### Projets

```http
POST /projects
GET /projects
GET /projects/{project_id}
PATCH /projects/{project_id}
DELETE /projects/{project_id}
```

### Media

```http
POST /projects/{project_id}/media
GET /projects/{project_id}/media
POST /media/{media_id}/probe
POST /media/{media_id}/proxy
```

### Pipeline

```http
POST /projects/{project_id}/jobs/import
POST /projects/{project_id}/jobs/transcribe
POST /projects/{project_id}/jobs/align
POST /projects/{project_id}/jobs/generate-rythmo
GET /jobs/{job_id}
POST /jobs/{job_id}/cancel
```

### Transcript

```http
GET /projects/{project_id}/transcript
PATCH /projects/{project_id}/segments/{segment_id}
PATCH /projects/{project_id}/words/{word_id}
POST /projects/{project_id}/segments
DELETE /projects/{project_id}/segments/{segment_id}
```

### Rythmo

```http
GET /projects/{project_id}/rythmo
PATCH /projects/{project_id}/rythmo/settings
POST /projects/{project_id}/rythmo/rebuild
```

### Exports

```http
POST /projects/{project_id}/exports
GET /projects/{project_id}/exports
GET /exports/{export_id}/download
```

### WebSocket

```text
ws://localhost:8000/ws/projects/{project_id}
```

Evenements :

```json
{
  "type": "job.progress",
  "job_id": "job_123",
  "stage": "alignment",
  "progress": 0.72,
  "message": "Alignement des mots"
}
```

## 7. Modele de Donnees

### Project

- id
- name
- created_at
- updated_at
- language
- frame_rate
- status
- settings_json

### MediaAsset

- id
- project_id
- kind: source, proxy, audio_asr, audio_master, thumbnail, waveform
- path
- duration
- fps
- width
- height
- codec
- hash

### Segment

- id
- project_id
- speaker_id
- start_time
- end_time
- text
- confidence
- source: asr, user, import
- locked

### Word

- id
- segment_id
- index
- text
- normalized_text
- start_time
- end_time
- confidence
- x
- y
- width
- lane
- locked

### Speaker

- id
- project_id
- name
- color
- voice_hint

### RythmoSettings

- project_id
- pixels_per_second
- font_family
- font_size
- lane_height
- text_color
- background_color
- show_confidence
- safe_area

### ExportJob

- id
- project_id
- format
- status
- path
- settings_json
- created_at
- completed_at
- error

## 8. Interface Utilisateur

### Ecran Principal

Disposition recommandee :

- barre superieure : projet, import, sauvegarde, export, parametres ;
- panneau gauche : fichiers, locuteurs, versions ;
- zone centrale haute : lecteur video ;
- zone centrale basse : bande rythmo canvas ;
- panneau droit : propriete du mot/segment selectionne ;
- bas de page : timeline, zoom, timecode, statut job.

### Import

Fonctions :

- glisser-deposer video ;
- choix langue ;
- choix moteur ASR local ;
- selection qualite transcription ;
- bouton lancer analyse ;
- progression detaillee par etape.

### Editeur Rythmo

Interactions :

- drag horizontal pour retimer ;
- drag bord gauche/droit pour ajuster debut/fin ;
- double clic pour editer le texte ;
- selection multiple ;
- raccourcis clavier ;
- snap sur frames, mots voisins, silences ;
- couleurs par locuteur ;
- indicateur de confiance.

### Export

Panneau d'export :

- format ;
- resolution ;
- codec ;
- inclusion video ;
- inclusion bande transparente ;
- chemin de sortie ;
- preset studio ;
- rapport de validation.

## 9. Algorithmes Cles

### Detection Silences

- calcul RMS court terme ;
- seuil adaptatif ;
- regroupement des intervalles silencieux ;
- utilisation pour segmenter et suggerer respirations.

### Alignement Fallback

Quand aucun alignement mot fiable n'est disponible :

```text
duration = segment.end - segment.start
weights = phonetic_or_character_weight(words)
word_duration = duration * word_weight / total_weight
```

Puis :

- appliquer marges minimales ;
- corriger chevauchements ;
- lisser les transitions ;
- marquer comme basse confiance.

### Layout Rythmo

Le layout doit etre deterministe :

- meme entree = meme sortie ;
- tous les mots ont une boite temporelle ;
- les coordonnees sont recalculees selon zoom et viewport ;
- les donnees temporelles restent separees des donnees visuelles.

### Synchronisation

La video pilote le temps :

- `requestAnimationFrame` cote frontend ;
- lecture `HTMLVideoElement.currentTime` ;
- interpolation visuelle du playhead ;
- correction drift sur pause/seek/playback rate.

## 10. Optimisations CPU/GPU

### CPU

- decouper l'audio en chunks ;
- paralleliser transcription par segments VAD ;
- cache des resultats intermediaires ;
- eviter recalcul layout complet a chaque frame ;
- index temporel des mots par intervalle ;
- rendu canvas par tuiles.

### GPU

- utiliser CUDA, Metal ou Vulkan si le moteur ASR local le permet ;
- llama.cpp avec acceleration GPU optionnelle ;
- WebGL ou OffscreenCanvas pour rendu avance ;
- encodage materiel FFmpeg si disponible :
  - NVENC ;
  - QuickSync ;
  - VideoToolbox ;
  - AMF.

### Memoire

- ne jamais charger la video complete en RAM ;
- streaming frames uniquement pour export ;
- thumbnails et waveform precomputees ;
- purge des caches temporaires par projet.

## 11. Usage de llama.cpp

llama.cpp ne doit pas remplacer l'ASR ni l'alignement temporel. Il sert aux traitements linguistiques locaux.

Cas d'usage :

- ponctuation ;
- correction orthographique suggeree ;
- segmentation en phrases ;
- nomination automatique des personnages ;
- resume du projet ;
- detection incoherences transcription/video ;
- adaptation texte source vers style doublage, si active explicitement.

Interface interne :

```python
class LocalLLMService:
    def punctuate(self, text: str, language: str) -> str: ...
    def split_dialogue(self, text: str) -> list[DialogueUnit]: ...
    def suggest_speaker_names(self, segments: list[Segment]) -> list[SpeakerHint]: ...
```

Contraintes :

- modele stocke dans `data/models/`;
- execution optionnelle ;
- journalisation des prompts ;
- aucun envoi reseau ;
- limite stricte de contexte pour performance.

## 12. Securite et Confidentialite

- aucun upload externe ;
- chemins de fichiers normalises ;
- API limitee a localhost ;
- CORS restreint ;
- logs sans contenu sensible par defaut ;
- suppression securisee des temporaires optionnelle ;
- verification des extensions et codecs ;
- prevention traversal path.

## 13. Tests

### Unitaires

- parsing FFprobe ;
- conversion timecode ;
- alignement fallback ;
- layout rythmo ;
- exports SRT/VTT/JSON.

### Integration

- import video courte ;
- extraction audio ;
- transcription mockee ;
- generation bande ;
- export complet.

### End-to-End

- ouvrir projet ;
- importer video ;
- lancer pipeline ;
- corriger un mot ;
- lire synchronise ;
- exporter video et sous-titres.

### Performance

Mesures cibles V1 :

- import metadata < 5 s ;
- waveform video 10 min < 60 s ;
- navigation timeline fluide ;
- rendu canvas > 30 fps ;
- export video au moins 0.5x temps reel CPU, mieux avec GPU.

## 14. Monetisation

Modeles possibles :

- licence perpetuelle par poste ;
- abonnement professionnel ;
- edition gratuite limitee ;
- pack studio multi-postes ;
- modules payants :
  - exports broadcast ;
  - batch processing ;
  - collaboration reseau local ;
  - dictionnaires metier ;
  - profils de personnages ;
  - templates de bandes ;
  - acceleration GPU avancee ;
  - support prioritaire.

Segmentation commerciale :

- Solo : projets courts, exports standards ;
- Pro : exports video, presets studio, modeles locaux optimises ;
- Studio : batch, profils equipe, licences flottantes, integration NAS ;
- Enterprise : support, deploiement controle, formats proprietaires.

## 15. Plan de Developpement

### Phase 0 - Prototype Technique, 2 a 3 semaines

- serveur FastAPI local ;
- import video ;
- extraction audio FFmpeg ;
- ASR local branche ;
- affichage transcript brut ;
- canvas rythmo minimal ;
- lecture video synchronisee.

Livrable : preuve que le pipeline local fonctionne.

### Phase 1 - MVP Utilisable, 6 a 8 semaines

- gestion projets SQLite ;
- jobs avec progression ;
- alignement mot par mot ;
- edition texte et timing ;
- sauvegarde auto ;
- exports JSON, SRT, VTT ;
- UI stable ;
- tests unitaires principaux.

Livrable : outil utilisable sur vrais projets courts.

### Phase 2 - Version Pro Beta, 8 a 12 semaines

- proxy video ;
- waveform ;
- gestion locuteurs ;
- undo/redo ;
- rendu bande avance ;
- export video incruste ;
- presets d'export ;
- integration llama.cpp optionnelle ;
- packaging desktop interne ;
- tests E2E.

Livrable : beta fermee pour utilisateurs metier.

### Phase 3 - Version Commerciale 1.0, 12 a 16 semaines

- installateur ;
- licence locale ;
- documentation utilisateur ;
- crash reports locaux exportables ;
- benchmark materiel ;
- validation exports ;
- onboarding ;
- compatibilite Windows/macOS prioritaire ;
- suite de tests regression ;
- politique de migration projets.

Livrable : version distribuable et vendable.

### Phase 4 - Croissance Produit

- batch processing ;
- collaboration locale ;
- formats studio specifiques ;
- plugins d'import/export ;
- modele de templates ;
- integration surfaces de controle ;
- marketplace presets ;
- edition multi-langue.

## 16. Risques Techniques

### Qualite ASR

Risque : transcription insuffisante sur audio bruite ou dialogues superposes.

Mitigation :

- choix moteur interchangeable ;
- indicateurs confiance ;
- correction rapide ;
- VAD et denoise optionnels.

### Alignement Mot

Risque : timings inexacts.

Mitigation :

- forced alignment local ;
- fallback transparent ;
- outils de retiming efficaces ;
- verrouillage utilisateur.

### Performance Export

Risque : rendu video lent.

Mitigation :

- pipeline FFmpeg direct ;
- encodage materiel ;
- rendu par segments ;
- cache frames statiques.

### Complexite UI

Risque : outil trop complexe pour adoption.

Mitigation :

- workflow guide ;
- raccourcis professionnels ;
- interface dense mais claire ;
- presets par usage.

## 17. Definition de Pret a Distribuer

Une version est prete a etre distribuee quand :

- installation en moins de 5 minutes ;
- ouverture et import d'une video standard sans configuration manuelle ;
- pipeline complet local fonctionne hors ligne ;
- exports essentiels valides ;
- aucun crash sur projet de 30 minutes ;
- sauvegarde fiable ;
- documentation utilisateur incluse ;
- performances mesurees et affichees ;
- licence et conditions commerciales integrees ;
- tests automatiques passent sur Windows et macOS.

## 18. Priorite d'Implementation Recommandee

Ordre pragmatique :

1. backend FastAPI et modele projet ;
2. import video + FFprobe ;
3. extraction audio ;
4. ASR local branche derriere interface abstraite ;
5. transcript et mots en base ;
6. frontend lecteur video ;
7. canvas bande rythmo synchronise ;
8. edition timings/texte ;
9. exports SRT/VTT/JSON ;
10. export video ;
11. llama.cpp pour enrichissement linguistique ;
12. packaging commercial.

Cette sequence evite de construire une interface avancee avant de valider la chaine media, qui est le coeur du produit.

