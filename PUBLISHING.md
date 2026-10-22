# Publishing the Chapman Notary Services website

The whole site lives in the `docs/` folder (`index.html` + `thanks.html`). No build step.

**Recommended: Netlify.** It's free, and the booking form works there (on GitHub Pages it doesn't, but the call/text/email buttons still do).

---

## Before you publish: check these

1. **Commission dates.** The site says your commission expires **October 19, 2026**. If you've renewed, update the date in `docs/index.html` (it appears in the About section and the footer). Search the file for `October 19, 2026`.
2. **Electronic notarization.** The fee table lists electronic notarization (up to $25). Only keep that row if you're registered with the NYS Department of State as an electronic notary. Otherwise delete the `<tr>` that says "Electronic notarization".
3. **Hours and service area.** Currently "Mon–Sat, 8am–8pm, by appointment only" and "Erie & Cattaraugus Counties". Edit in `docs/index.html` if different.

To edit: open the file on GitHub, click the pencil icon, change the text, click **Commit changes**.

---

## Option A: Netlify (recommended)

### 1. Put the site online
1. Go to <https://app.netlify.com/signup> and sign up with your GitHub account.
2. Click **Add new site → Import an existing project → GitHub**.
3. Pick the repository `thomaschapmanre/claude-ai-` and the branch the site is on (`main` once merged).
4. Settings:
   - **Build command:** leave empty
   - **Publish directory:** `docs`
5. Click **Deploy**. In about 30 seconds you get a free address like `something-random.netlify.app`.
6. Optional: **Site configuration → Change site name** to get `chapmannotary.netlify.app`.

Every time you edit the files on GitHub, Netlify re-publishes automatically.

### 2. Turn on form email notifications
1. Submit a test request from your live site once.
2. In Netlify: **Site configuration → Forms → Enable form detection** (if it's not already on), then **Forms → Form notifications → Add notification → Email notification**.
3. Enter `Thomas.chapmanre@gmail.com`. Booking requests now land in your inbox. The free plan includes 100 submissions/month.

### 3. Connect your domain

**If you still need to buy `chapmannotary.com`:**
The easiest path is to buy it inside Netlify: **Domain management → Add a domain → type `chapmannotary.com` → Register**. Netlify sets up everything (DNS + HTTPS) automatically. About $12–20/year. You're done; skip the rest of this step.

(Cheaper alternatives: Cloudflare Registrar or Porkbun, around $10–11/year. Then follow the steps below.)

**If you already own it (bought somewhere else, like GoDaddy, Namecheap, Porkbun):**
1. In Netlify: **Domain management → Add a domain → `chapmannotary.com` → Verify → Add domain**.
2. Netlify shows DNS records to add. Log in to where you bought the domain, open its **DNS settings**, and add:

   | Type  | Name / Host | Value |
   |-------|-------------|-------|
   | A     | `@`         | `75.2.60.5` |
   | CNAME | `www`       | `your-site-name.netlify.app` |

   Delete any older `A` record for `@` or `CNAME` for `www` (often "parked" page records). Use the exact values Netlify shows you if they differ from these.
3. Wait from 10 minutes to a few hours. Netlify then issues a free HTTPS certificate on its own (**Domain management → HTTPS** shows the status).

---

## Option B: GitHub Pages (free, but no booking form)

1. On GitHub, open the repository → **Settings → Pages**.
2. Under **Build and deployment**: Source = **Deploy from a branch**, Branch = `main`, Folder = `/docs`. Click **Save**.
3. After a minute the site is at `https://thomaschapmanre.github.io/claude-ai-/`.
4. Remove the form (it won't work here): in `docs/index.html`, delete everything from `<h3>Or send a request</h3>` through `</form>`.

**Connect your domain:**
1. In **Settings → Pages → Custom domain**, enter `chapmannotary.com` and click **Save**.
2. At your domain registrar's DNS settings add:

   | Type  | Name / Host | Value |
   |-------|-------------|-------|
   | A     | `@`         | `185.199.108.153` |
   | A     | `@`         | `185.199.109.153` |
   | A     | `@`         | `185.199.110.153` |
   | A     | `@`         | `185.199.111.153` |
   | CNAME | `www`       | `thomaschapmanre.github.io` |

3. Once GitHub shows the DNS check passed, tick **Enforce HTTPS**.

---

## Compliance notes (already built in)

- Fees: $2 per signature; electronic notarization capped at $25; travel fee listed separately and agreed in advance.
- "Not an attorney" disclaimer appears in the About section and the footer, using the wording from NYS Executive Law §135-c.
- The site is English-only and never uses the phrase "notario público". If you ever add a page in another language, that page must also show the §135-c disclaimer and the fee schedule (in that language), and must still never use "notario público" or similar terms.
