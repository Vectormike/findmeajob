from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from findmeajob.tools.browser import Blocked, FormSession
from findmeajob.tools.browser_ats import STRATEGIES
from findmeajob.tools.chrome import Chrome


async def test_form_session_handles_custom_controls_and_multiple_steps(tmp_path: Path):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <main id="form">
              <label>Name <input name="name" required></label>
              <div role="combobox" contenteditable="true" aria-label="Location"
                   aria-controls="locations" aria-required="true"></div>
              <input required tabindex="-1" aria-hidden="true" style="opacity: 0">
              <div id="locations" role="listbox"><div role="option">Berlin</div></div>
              <button type="button" onclick="stepTwo()">Next</button>
            </main>
            <script>
              function stepTwo() {
                document.querySelector('main').innerHTML = `
                  <div role="radiogroup" aria-label="Work authorization" aria-required="true">
                    <div role="radio">Yes</div><div role="radio">No</div>
                  </div>
                  <label>Why us? <textarea required></textarea></label>
                  <button type="submit" onclick="submitted(event)">Submit application</button>`;
              }
              function submitted(event) {
                event.preventDefault();
                document.body.innerHTML = '<h1>Thanks for applying</h1>';
              }
            </script>
            """
        )
        session = FormSession(page)

        first = await session.fields()
        assert [field["type"] for field in first] == ["input", "combobox"]
        await session.fill(first, {"f0": "Ada Lovelace", "f1": "Berlin"}, tmp_path / "cv.pdf")
        assert (await session.advance())["status"] == "advanced"

        second = await session.fields()
        assert [field["type"] for field in second] == ["radio", "textarea"]
        await session.fill(second, {"g0": "Yes", "f3": "I build reliable systems."}, tmp_path / "cv.pdf")
        outcome = await session.advance()

        assert outcome["status"] == "submitted"
        assert outcome["confirmation"]["confirmed"] == "yes"
        await browser.close()


async def test_a_styled_resume_upload_gets_the_cv(tmp_path: Path):
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(b"%PDF-1.4")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <label>Email <input type="email"></label>
            <button type="button">Upload resume</button>
            <div class="file-input-container" style="height:0">
              <input name="cResume" type="file" style="display:none" required></div>
            <div style="display:none"><input name="photo" type="file"></div>
            """
        )
        session = FormSession(page)

        fields = await session.fields()
        await session.fill(fields, {}, cv)

        assert [field["label"] for field in fields if field["type"] == "file"] == ["cResume"]
        assert await page.eval_on_selector("[name=cResume]", "el => el.files[0].name") == "cv.pdf"
        await browser.close()


async def test_a_stuck_fill_times_out_and_frees_chrome_for_the_next(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("findmeajob.tools.chrome.FILL_TIMEOUT_SECONDS", 2)
    chrome = Chrome(tmp_path / "profile", headless=True)
    page = tmp_path / "form.html"
    page.write_text("<label>Email <input type='email'></label>")
    try:
        with pytest.raises(TimeoutError):
            async with chrome.fill_form(page.as_uri()) as session:
                await session.page.evaluate("new Promise(() => {})")
        async with chrome.fill_form(page.as_uri()) as session:
            assert len(await session.fields()) == 1
    finally:
        await chrome.close()


async def test_a_slow_location_search_picks_the_closest_suggestion(tmp_path: Path):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <label>Email <input type="email"></label>
            <label for="city">City</label>
            <input id="city" role="combobox" aria-autocomplete="list">
            <div id="menu"></div>
            <p id="picked"></p>
            <button type="submit" disabled>Submit application</button>
            <script>
              const menu = document.querySelector('#menu');
              document.querySelector('#city').oninput = () => setTimeout(() => {
                menu.innerHTML = '<div role="option">New Berlin, Wisconsin</div>'
                  + '<div role="option">Berlin, Germany</div>';
                menu.querySelectorAll('[role=option]').forEach((option) => option.onclick = () => {
                  document.querySelector('#picked').textContent = option.textContent;
                });
              }, 1500);
            </script>
            """
        )
        session = FormSession(page)
        fields = await session.fields()
        await session.fill(fields, {fields[1]["id"]: "Berlin"}, tmp_path / "cv.pdf")

        assert await page.locator("#picked").inner_text() == "Berlin, Germany"
        outcome = await session.advance()
        assert outcome["status"] == "validation"
        assert "still disabled" in outcome["errors"][0]
        await browser.close()


async def test_a_closed_dropdown_is_opened_to_read_its_options():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <label>Email <input type="email" required></label>
            <label for="rtw">Right to work</label>
            <input id="rtw" role="combobox" aria-autocomplete="list" required>
            <div id="menu"></div>
            <script>
              const menu = document.querySelector('#menu');
              document.querySelector('#rtw').onfocus = () => {
                menu.innerHTML = '<div role="option">Citizen</div><div role="option">Needs sponsorship</div>';
              };
              document.onkeydown = (event) => { if (event.key === 'Escape') menu.innerHTML = ''; };
            </script>
            """
        )

        fields = await FormSession(page).fields()

        assert [o["label"] for o in fields[1]["options"]] == ["Citizen", "Needs sponsorship"]
        assert await page.locator("[role='option']").count() == 0
        await browser.close()


CAPTCHA_FORM = """
<label>Email <input type="email" required></label>
<div class="g-recaptcha" data-sitekey="site" style="width: 304px; height: 78px"></div>
<textarea name="g-recaptcha-response" hidden></textarea>
<button type="submit">Submit</button>
"""


async def test_a_captcha_waits_for_a_person_then_continues():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(CAPTCHA_FORM)
        handed: list[bool] = []

        async def handoff(_: object, waiting: bool) -> None:
            handed.append(waiting)
            if waiting:
                await page.evaluate("document.querySelector('[name=g-recaptcha-response]').value = 'token'")

        fields = await FormSession(page, handoff).fields()

        assert handed == [True, False]
        assert "Email" in [field["label"] for field in fields]
        await browser.close()


async def test_an_emailed_security_code_waits_for_a_person_then_confirms():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <form id="form" onsubmit="event.preventDefault(); askForCode()">
              <label>Email <input type="email" value="ada@example.com"></label>
              <button type="submit">Submit application</button>
            </form>
            <script>
              function askForCode() {
                document.body.innerHTML = `<label>Security code <input id="code"></label>
                  <button onclick="document.body.innerHTML = '<h1>Thank you for applying</h1>'">Submit</button>`;
              }
            </script>
            """
        )
        handed: list[bool] = []

        async def handoff(_: object, waiting: bool) -> None:
            handed.append(waiting)
            if waiting:
                await page.fill("#code", "91395230")
                await page.click("text=Submit")

        session = FormSession(page, handoff)
        await session.fields()
        outcome = await session.advance()

        assert handed == [True, False]
        assert outcome["status"] == "submitted"
        await browser.close()


async def test_a_submit_that_leaves_the_form_open_is_not_treated_as_sent():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <label>Email <input type="email" value="ada@example.com"></label>
            <button type="button">Submit application</button>
            """
        )

        outcome = await FormSession(page).advance()

        assert outcome["status"] == "validation"
        assert "not accepted" in outcome["errors"][0]
        await browser.close()


async def test_an_ashby_success_container_counts_without_the_usual_words():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.route(
            "**/*",
            lambda route: route.fulfill(
                body='<div class="ashby-application-form-success-container"><p>You are all set.</p></div>',
                content_type="text/html",
            ),
        )
        await page.goto("https://jobs.ashbyhq.com/acme/job/application")

        confirmation = await FormSession(page)._confirmation()

        assert confirmation["confirmed"] == "yes"
        await browser.close()


async def test_a_captcha_without_a_person_blocks():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(CAPTCHA_FORM)

        with pytest.raises(Blocked, match="bot check"):
            await FormSession(page).fields()
        await browser.close()


async def test_an_invisible_recaptcha_badge_is_not_a_captcha():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <label>Email <input type="email" required></label>
            <div class="grecaptcha-badge" style="width: 256px; height: 60px">
              <iframe src="https://www.recaptcha.net/recaptcha/enterprise/anchor?k=site&size=invisible"></iframe>
            </div>
            <textarea class="g-recaptcha-response" style="display: none"></textarea>
            """
        )

        assert len(await FormSession(page).fields()) == 1
        await browser.close()


async def test_apply_behind_a_sign_in_blocks_instead_of_filling_site_toggles():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <label>Dark mode <input type="checkbox"></label>
            <button onclick="document.querySelector('dialog').showModal()">Apply now</button>
            <dialog><p>Sign in to continue</p><button>Sign in</button></dialog>
            """
        )

        with pytest.raises(Blocked, match="sign-in"):
            await FormSession(page).fields()
        await browser.close()


async def test_a_sign_in_page_without_a_password_box_yet_blocks():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.route("**/*", lambda route: route.fulfill(body="<label>Email or phone <input></label>"))
        await page.goto("https://login.microsoftonline.com/common/oauth2/authorize")

        with pytest.raises(Blocked, match="login"):
            await FormSession(page).fields()
        await browser.close()


async def test_a_google_sign_in_waits_for_a_person_then_reads_the_form():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.route("https://accounts.google.com/**", lambda route: route.fulfill(body="<input>"))
        await page.route(
            "https://docs.google.com/**",
            lambda route: route.fulfill(body="<label>Full name <input></label>", content_type="text/html"),
        )
        await page.goto("https://accounts.google.com/v3/signin/identifier")
        handed: list[bool] = []

        async def handoff(_: object, waiting: bool) -> None:
            handed.append(waiting)
            if waiting:
                await page.goto("https://docs.google.com/forms/d/e/form/viewform")

        fields = await FormSession(page, handoff).fields()

        assert handed == [True, False]
        assert [field["label"] for field in fields] == ["Full name"]
        await browser.close()


async def test_a_google_sign_in_without_a_person_blocks():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.route("**/*", lambda route: route.fulfill(body="<input>"))
        await page.goto("https://accounts.google.com/v3/signin/identifier")

        with pytest.raises(Blocked, match="Google sign-in"):
            await FormSession(page).fields()
        await browser.close()


async def test_a_job_page_div_named_apply_opens_the_form():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <input placeholder="Search jobs">
            <input placeholder="Location">
            <div class="button action-apply">Apply for this job</div>
            <div class="button">Next job</div>
            <form id="application" hidden>
              <label>Email <input type="email" required></label>
              <button type="submit">Submit</button>
            </form>
            <script>
              document.querySelector('.action-apply').onclick = () => {
                document.querySelector('#application').hidden = false;
              };
            </script>
            """
        )
        session = FormSession(page)

        fields = await session.fields()

        assert "Email" in [field["label"] for field in fields]
        await browser.close()


@pytest.mark.parametrize(
    ("strategy_name", "button", "success"),
    [
        ("greenhouse", '<button id="submit_app">Apply</button>', '<p id="application_confirmation">Done</p>'),
        ("lever", '<button data-qa="submit-button">Apply</button>', '<p data-qa="application-success">Done</p>'),
        ("ashby", '<button data-testid="submit-job">Apply</button>', '<p data-testid="success">Done</p>'),
        (
            "workday",
            '<button data-automation-id="bottom-navigation-submit-button">Apply</button>',
            '<p data-automation-id="applicationConfirmation">Done</p>',
        ),
    ],
)
async def test_ats_submit_and_confirmation_selectors(strategy_name: str, button: str, success: str):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            f"""
            <form onsubmit="event.preventDefault(); this.hidden=true; document.querySelector('p').hidden=false">
              <label>Name <input required></label><label>Email <input required></label>{button}
            </form>
            {success.replace('>', ' hidden>', 1)}
            """
        )
        session = FormSession(page)
        session.strategy = next(strategy for strategy in STRATEGIES if strategy.name == strategy_name)
        fields = await session.fields()
        await session.fill(fields, {"f0": "Ada", "f1": "ada@example.com"}, Path("cv.pdf"))

        outcome = await session.advance()

        assert outcome["status"] == "submitted"
        await browser.close()
