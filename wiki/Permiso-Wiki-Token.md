<div align="center">

# 🔑 Guide: Give the Copilot agent write permission on the Wiki

### *How to grant GitHub Copilot Coding Agent the token needed to edit `Pecunator.wiki.git`*

![GitHub](https://img.shields.io/badge/GitHub-PAT-181717?style=for-the-badge&logo=github)
![Security](https://img.shields.io/badge/Scope-wiki%20write-orange?style=for-the-badge&logo=githubactions)
![Difficulty](https://img.shields.io/badge/difficulty-easy-brightgreen?style=for-the-badge)

</div>

---

## 🧩 Why is it necessary?

The **GitHub Copilot Coding Agent** receives an automatic installation token (`GITHUB_TOKEN`) which — by GitHub security design — **does not include write permissions to the Wiki**.

The Wiki on GitHub is a separate Git repository (`<your-repo>.wiki.git`) and requires a specific scoped token or PAT from the repository owner. Without it, any `git push` to the wiki fails with:

```
remote: Permission to CuevazaArt/Pecunator.wiki.git denied
fatal: unable to access '...': The requested URL returned error: 403
```

> 📖 Official reference: [GitHub Docs — About wikis](https://docs.github.com/en/communities/documenting-your-project-with-wikis/about-wikis) · [GitHub Apps Permissions](https://docs.github.com/en/rest/overview/permissions-required-for-github-apps)

---

## 🗺️ Options Overview

| Option | Effort | Security | Recommended |
|--------|----------|-----------|:-----------:|
| **A — classic PAT `repo`** | ⚡ 5 min | 🟡 Medium (wide scope) | To start quickly |
| **B — Fine-grained PAT** | ⚡ 8 min | 🟢 High (minimum scope) | ✅ **Recommended** |
| **C — Manual Sync from PR** | 🐢 manual | 🟢 High | For occasional use |

---

## ✅ Option B — Fine-Grained PAT *(recommended)*

### Step 1 — Create the token on GitHub

1. Go to **[github.com → Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)**.

> Direct path: `https://github.com/settings/tokens?type=beta`

2. Press **"Generate new token"**.

3. Fill in the fields:

| Field | Value |
   |-------|-------|
   | **Token name** | `pecunator-wiki-write` |
   | **Expiration** | 90 days (or whatever you prefer) |
   | **Resource owner** | `CaveArt` |
   | **Repository access** | ✅ Only selected repositories → **Pecunator** |

4. In **Repository permissions** search for **"Contents"** and select **"Read and write"**.

> ⚠️ The wiki lives under the `Contents` scope (it is a git repository). **You don't** need to enable "Pages", "Issues" or anything else.

5. Click **"Generate token"**.

6. 🟥 **COPY token now** — GitHub doesn't show it again.

The token will look like this:
   ```
   github_pat_11AAAAAAA_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

### Step 2 — Save the token as the repository's Secret

1. Go to the repository page:  
   `https://github.com/CuevazaArt/Pecunator/settings/secrets/actions`

2. Press **"New repository secret"**.

3. Fill:

| Field | Value |
   |-------|-------|
   | **Name** | `WIKI_WRITE_TOKEN` |
   | **Secret** | Paste the token from the previous step |

4. Press **"Add secret"**.

---

### Step 3 — Expose it to the agent in `copilot-setup-steps.yml`

The Copilot agent only has access to secrets that are explicitly exposed to it in the environment configuration file. Edit (or create) the `.github/copilot-setup-steps.yml` file:

```yaml
# .github/copilot-setup-steps.yml
steps:
  - name: Expose wiki write token
    env:
      WIKI_WRITE_TOKEN: ${{ secrets.WIKI_WRITE_TOKEN }}
    run: |
      echo "WIKI_WRITE_TOKEN=${WIKI_WRITE_TOKEN}" >> "$GITHUB_ENV"
```

> 📖 Reference: [GitHub Docs — Copilot coding agent setup steps](https://docs.github.com/en/copilot/managing-copilot/managing-github-copilot-in-your-organization/customizing-copilot-coding-agent-with-mcp/configuring-copilot-coding-agent-setup-steps)

---

### Step 4 — Verify that the agent can push

The next time the agent needs to publish the wiki, it will use the token like this:

```bash
git clone "https://x-access-token:${WIKI_WRITE_TOKEN}@github.com/CuevazaArt/Pecunator.wiki.git" /tmp/wiki
cp wiki/*.md /tmp/wiki/
cd /tmp/wiki
git add .
git commit -m "Sync wiki from main"
git push origin master
```

With the correct token, the push will succeed instead of the 403 error.

---

## ⚡ Option A — Classic PAT `repo` *(faster)*

> Use it if you want to get started in 5 minutes without worrying about granularity.  
> Limitation: the `repo` scope gives write access to **all** your private repositories, not just Pecunator.

1. Go to **[github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)**.
2. Press **"Generate new token (classic)"**.
3. Check the **`repo`** scope (includes `repo:status`, `repo_deployment`, `public_repo`, `repo:invite`, `security_events`).
4. Copy the token and save it as secret `WIKI_WRITE_TOKEN` same as Option B, Step 2.
5. Add the same block in `.github/copilot-setup-steps.yml`.

---

## 🐢 Option C — Manual Sync from the PR *(no configuration)*

If you prefer not to create additional tokens, the flow is:

1. The agent writes the `.md` files to `wiki/` within the PR branch (as it does today).
2. You copy them to the wiki manually on your machine:

```bash
# Clone the wiki only once
git clone https://github.com/CuevazaArt/Pecunator.wiki.git

# After each PR, copy the files
cp <path-to-PR>/wiki/*.md Pecunator.wiki/

# Publish
cd Pecunator.wiki
git add .
git commit -m "Sync wiki from PR #X"
git push
```

Or faster, directly from the web editor:  
`https://github.com/CuevazaArt/Pecunator/wiki/<Page-Name>/_edit`

---

## 🔒 Good security practices

| ✅ Make | ❌ Avoid |
|---------|---------|
| Use fine-grained PAT with minimal scope | Classic PAT with scope `admin` |
| Set expiration (90 days) | Tokens without expiration |
| Save the token as Secret, not in code | Put token in `copilot-setup-steps.yml` in plain text |
| Revoke token if not in use | Leave tokens active indefinitely |
| Rotate token before expiration | Forget the expiration date |

> 📖 See also: **[Security and Credentials](Security-and-Credentials)** in this wiki.  
> 📖 NIST SP 800-57 (key management): [csrc.nist.gov](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)

---

## 🔍 How to verify that the token is active

```bash
# Desde tu terminal local, comprueba que el token tiene acceso
curl -H "Authorization: token <tu-token>" \
     https://api.github.com/repos/CuevazaArt/Pecunator \
     | python3 -m json.tool | grep '"permissions"' -A 10
```

You should see `"push": true`. If you see `"push": false` the token does not have the correct permissions.

---

## 📋 Deployment checklist

```
□ Paso 1 — Creado fine-grained PAT con Contents: Read and Write
□ Paso 2 — PAT guardado como secret WIKI_WRITE_TOKEN en el repo
□ Paso 3 — .github/copilot-setup-steps.yml actualizado para exponer el secret
□ Paso 4 — Verificado con curl que el token tiene push: true
□ Recordatorio en calendario para rotar antes de la expiración
```

---

<div align="center">

**[⬆️ Home](Home)** · **[🔐 Security and Credentials](Security-and-Credentials)** · **[🛠️ Development Guide](Development-Guide)**

<sub>📌 This guide only applies to the owner of the repository (<strong>CuevazaArt</strong>). Tokens should never be shared.</sub>

</div>