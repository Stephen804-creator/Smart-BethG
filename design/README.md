# Smart BethG design folder

Rules for AI agents (read first): DESIGN.md, LAB.md, MENTOR.md, WEBSITE.md. Tokens: tokens.json.

## Mockups (HTML, the source of truth for how the app looks)
- mockups/phone-app.html: the whole phone app (open it and tap through).
- mockups/lab-desktop.html: the desktop/tablet Lab IDE (Software, Hardware, Both).
- mockups/website.html: the marketing website with the collapsible menu.

They need these files next to them (upload from the design zip): mockups/logo.png and mockups/img/home.png, lesson.png, battle.png, lab-hardware.png.

## PNG screens
PNGs are generated from the HTML. Run `python design/render_screens.py` to rebuild them into design/screens/. Do not edit PNGs by hand; change the HTML, then re-render.

## Change process
Update the mockup HTML first, then update the matching rules file, then write the code.
