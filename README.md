cd ~/DeckOps-Nightly-dev
git add src/iw5_downgrade.py src/ui_constants.py src/ui_install.py src/ui_manage.py src/ui_qt.py
git commit -m "feat: MW3 32-bit downgrade for Plutonium compatibility

Activision pushed a 64-bit update for MW3 that breaks Plutonium.
Two downgrade paths: QR code scan via DepotDownloader (recommended)
or manual Steam console paste. Both merge 32-bit depot files over
the game install and proceed to Plutonium reinstall.

QR path: downloads DepotDownloader, captures QR for Steam mobile
app auth, handles QR refresh, deletes tool + credentials after.
Manual path: opens Steam console, clipboard-assists two commands.

New file: iw5_downgrade.py
Modified: ui_constants.py, ui_install.py, ui_manage.py, ui_qt.py"
git push
