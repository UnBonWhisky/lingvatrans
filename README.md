# lingvatrans

Lingvatrans is an asynchronous translation library used to translate using the lingvanex service.

> **Note**: I have no intention to add features or to maintain this project except for a personal use. This is a temporary solution to a temporary a problem. If you have ideas to maintain this project, your help is welcome

## Installation

### PyPI

Actually I have not posted this project on pypi. The better way is to use the git install from pip

### Repository

You can install the project directly from this repository.

```shell
pip install git+https://github.com/UnBonWhisky/lingvatrans.git
```

## How to use

Here is an example code of how to use it :
```py
from lingvatrans import Translator
import asyncio

async def main():
    trad = Translator()
    translation = await trad.translate("Here is my code example", dest="fr")
    print(translation.text) # Voici mon exemple de code
    translation = await trad.detect("Un texte français")
    print(translation.lang) # fr
    await trad.close()

if __name__ == "__main__":
    asyncio.run(main())
```
