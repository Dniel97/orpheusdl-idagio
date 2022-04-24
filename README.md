<!-- PROJECT INTRO -->

OrpheusDL - Idagio
==================

An Idagio module for the OrpheusDL modular archival music program

[Report Bug](https://github.com/Dniel97/orpheusdl-idagio/issues)
·
[Request Feature](https://github.com/Dniel97/orpheusdl-idagio/issues)


## Table of content

- [About OrpheusDL - Idagio](#about-orpheusdl-idagio)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
    - [Global](#global)
    - [Idagio](#idagio)
- [Acknowledgements](#acknowledgements)
- [Contact](#contact)


<!-- ABOUT ORPHEUS -->
## About OrpheusDL - Idagio

OrpheusDL - Idagio is a module written in Python which allows archiving from **Idagio** for the modular music archival program.


<!-- GETTING STARTED -->
## Getting Started

Follow these steps to get a local copy of Orpheus up and running:

### Prerequisites

* Already have [OrpheusDL](https://github.com/yarrm80s/orpheusdl) installed

### Installation

1. Clone the repo inside the folder `orpheusdl/modules/`
   ```sh
   git clone https://github.com/Dniel97/orpheusdl-idagio.git modules/idagio
   ```
2. Execute:
   ```sh
   python orpheus.py
   ```
3. Now the `config/settings.json` file should be updated with the Idagio settings

<!-- USAGE EXAMPLES -->
## Usage

Just call `orpheus.py` with any link you want to archive:

```sh
python orpheus.py https://app.idagio.com/albums/the-berlin-concert-94856157-70B2-4DF4-B658-45AACFF2A5A3
```

<!-- CONFIGURATION -->
## Configuration

You can customize every module from Orpheus individually and also set general/global settings which are active in every
loaded module. You'll find the configuration file here: `config/settings.json`

### Global

```json5
"global": {
    "general": {
        // ...
        "download_quality": "hifi"
    },
    // ...
}
```

`download_quality`: Choose one of the following settings:
* "hifi": same as "lossless"
* "lossless": FLAC with 44.1kHz/16bit
* "high": same as "medium"
* "medium": AAC 320 kbit/s
* "low": same as "minimum"
* "minimum": AAC 160 kbit/s

### Idagio
```json5
"idagio": {
    "username": "",
    "password": ""
}
```

`username`: Enter your Idagio email address here

`password`: Enter your Idagio password here

<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements

Special thanks to [@uhwot](https://github.com/uhwot) for the help with the AES-CTR-128 decryption part.

<!-- Contact -->
## Contact

Dniel97 - [@Dniel97](https://github.com/Dniel97)

Project Link: [OrpheusDL Idagio Public GitHub Repository](https://github.com/Dniel97/orpheusdl-idagio)
