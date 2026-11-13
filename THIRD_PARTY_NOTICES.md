# Third-party notices

The Windows build (`Lim.exe`) bundles the following open-source components. Each keeps its own license;
the full texts ship with each package and are available from the links below.

## Python (bundled in the exe)

| Package | Version | License | Source |
|---|---|---|---|
| annotated-doc | 0.0.6 | MIT | https://github.com/fastapi/annotated-doc |
| annotated-types | 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.16.0 | MIT | https://anyio.readthedocs.io/en/latest/ |
| bottle | 0.13.4 | MIT License | http://bottlepy.org/ |
| certifi | 2026.10.23 | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/certifi/python-certifi |
| cffi | 2.1.1 | MIT-0 | https://cffi.readthedocs.io/ |
| click | 8.5.1 | BSD-3-Clause | https://click.palletsprojects.com/page/changes/ |
| clr_loader | 0.3.1 | MIT | https://github.com/pythonnet/clr-loader |
| colorama | 0.4.6 | BSD License | https://github.com/tartley/colorama |
| fastapi | 0.162.4 | MIT | https://github.com/fastapi/fastapi |
| h11 | 0.16.0 | MIT License | https://github.com/python-hyper/h11 |
| httpcore | 1.0.9 | BSD-3-Clause | https://www.encode.io/httpcore |
| httptools | 0.9.0 | MIT | https://github.com/MagicStack/httptools |
| httpx | 0.28.1 | BSD License | https://github.com/encode/httpx/blob/master/CHANGELOG.md |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna/blob/master/HISTORY.md |
| opentelemetry-api | 1.45.2 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| pillow | 13.0.0 | MIT-CMU | https://pillow.readthedocs.io/en/stable/releasenotes/index.html |
| proxy_tools | 0.1.0 | MIT License | http://github.com/jtushman/proxy_tools |
| pycparser | 3.12 | BSD-3-Clause | https://github.com/eliben/pycparser |
| pydantic | 2.14.3 | MIT | https://github.com/pydantic/pydantic |
| pydantic_core | 2.50.4 | MIT | https://github.com/pydantic/pydantic |
| pystray | 0.19.5 | GNU Lesser General Public License v3 (LGPLv3) | https://github.com/moses-palmer/pystray |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| pythonnet | 3.2.1 | MIT | https://pythonnet.github.io/ |
| pywebview | 6.2.1 | BSD License | https://pywebview.flowrl.com/ |
| PyYAML | 6.0.3 | MIT License | https://pyyaml.org/ |
| six | 1.17.0 | MIT License | https://github.com/benjaminp/six |
| starlette | 1.10.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| typing-inspection | 0.4.5 | MIT | https://github.com/pydantic/typing-inspection |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions/issues |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/release-notes |
| watchfiles | 1.3.0 | MIT License | https://github.com/samuelcolvin/watchfiles |
| websockets | 17.4 | BSD-3-Clause | https://github.com/python-websockets/websockets |
| Windows-Toasts | 1.3.1 | Apache-2.0 | https://github.com/DatGuy1/Windows-Toasts |
| winrt-runtime | 3.2.1 | MIT | https://pywinrt.readthedocs.io |
| winrt-Windows.Data.Xml.Dom | 3.2.1 | MIT | https://pywinrt.readthedocs.io |
| winrt-Windows.Foundation | 3.2.1 | MIT | https://pywinrt.readthedocs.io |
| winrt-Windows.Foundation.Collections | 3.2.1 | MIT | https://pywinrt.readthedocs.io |
| winrt-Windows.UI.Notifications | 3.2.1 | MIT | https://pywinrt.readthedocs.io |
| xxhash | 4.1.0 | BSD-2-Clause | https://github.com/ifduyue/python-xxhash |

pystray is licensed under the LGPL v3. It is used unmodified; its source is available at https://github.com/moses-palmer/pystray and you may replace it by rebuilding the exe from this repository (`tools/build_exe.py`).

The exe is built with PyInstaller (GPL v2 with the bootloader exception, which allows distributing the result under any license).

## Interface (bundled in `dm/static`)

| Package | License |
|---|---|
| @fontsource-variable/bricolage-grotesque | OFL-1.1 |
| @fontsource/ibm-plex-mono | OFL-1.1 |
| lucide-react | ISC |
| motion | MIT |
| react | MIT |
| react-dom | MIT |

Fonts: Bricolage Grotesque and IBM Plex Mono, SIL Open Font License 1.1 (via Fontsource).
