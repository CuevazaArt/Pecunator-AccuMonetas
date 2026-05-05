<div align="center">

# 🔑 Guía: Darle permiso de escritura al agente Copilot sobre el Wiki

### *Cómo conceder a GitHub Copilot Coding Agent el token necesario para editar `Pecunator.wiki.git`*

![GitHub](https://img.shields.io/badge/GitHub-PAT-181717?style=for-the-badge&logo=github)
![Security](https://img.shields.io/badge/Scope-wiki%20write-orange?style=for-the-badge&logo=githubactions)
![Difficulty](https://img.shields.io/badge/dificultad-fácil-brightgreen?style=for-the-badge)

</div>

---

## 🧩 ¿Por qué es necesario?

El **GitHub Copilot Coding Agent** recibe un token de instalación automático (`GITHUB_TOKEN`) que — por diseño de seguridad de GitHub — **no incluye permisos de escritura sobre el Wiki**.

El Wiki en GitHub es un repositorio Git separado (`<tu-repo>.wiki.git`) y requiere un token con scope específico o un PAT del propietario del repositorio. Sin él, cualquier `git push` al wiki falla con:

```
remote: Permission to CuevazaArt/Pecunator.wiki.git denied
fatal: unable to access '...': The requested URL returned error: 403
```

> 📖 Referencia oficial: [GitHub Docs — About wikis](https://docs.github.com/en/communities/documenting-your-project-with-wikis/about-wikis) · [GitHub Apps Permissions](https://docs.github.com/en/rest/overview/permissions-required-for-github-apps)

---

## 🗺️ Resumen de opciones

| Opción | Esfuerzo | Seguridad | Recomendada |
|--------|----------|-----------|:-----------:|
| **A — PAT clásico `repo`** | ⚡ 5 min | 🟡 Media (scope amplio) | Para empezar rápido |
| **B — Fine-grained PAT** | ⚡ 8 min | 🟢 Alta (scope mínimo) | ✅ **Recomendada** |
| **C — Sync manual desde PR** | 🐢 manual | 🟢 Alta | Para uso ocasional |

---

## ✅ Opción B — Fine-Grained PAT *(recomendada)*

### Paso 1 — Crear el token en GitHub

1. Ve a **[github.com → Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)**.

   > Ruta directa: `https://github.com/settings/tokens?type=beta`

2. Pulsa **"Generate new token"**.

3. Rellena los campos:

   | Campo | Valor |
   |-------|-------|
   | **Token name** | `pecunator-wiki-write` |
   | **Expiration** | 90 días (o el que prefieras) |
   | **Resource owner** | `CuevazaArt` |
   | **Repository access** | ✅ Only selected repositories → **Pecunator** |

4. En **Repository permissions** busca **"Contents"** y selecciona **"Read and write"**.

   > ⚠️ El wiki vive bajo el scope `Contents` (es un repositorio git). **No** necesitas habilitar "Pages", "Issues" ni ningún otro.

5. Haz clic en **"Generate token"**.

6. 🟥 **COPIA el token ahora** — GitHub no lo vuelve a mostrar.

   El token se verá así:
   ```
   github_pat_11AAAAAAA_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

### Paso 2 — Guardar el token como Secret del repositorio

1. Ve a la página del repositorio:  
   `https://github.com/CuevazaArt/Pecunator/settings/secrets/actions`

2. Pulsa **"New repository secret"**.

3. Rellena:

   | Campo | Valor |
   |-------|-------|
   | **Name** | `WIKI_WRITE_TOKEN` |
   | **Secret** | Pega el token del paso anterior |

4. Pulsa **"Add secret"**.

---

### Paso 3 — Exponerlo al agente en `copilot-setup-steps.yml`

El agente Copilot sólo tiene acceso a los secrets que se le exponen explícitamente en el archivo de configuración del entorno. Edita (o crea) el archivo `.github/copilot-setup-steps.yml`:

```yaml
# .github/copilot-setup-steps.yml
steps:
  - name: Expose wiki write token
    env:
      WIKI_WRITE_TOKEN: ${{ secrets.WIKI_WRITE_TOKEN }}
    run: |
      echo "WIKI_WRITE_TOKEN=${WIKI_WRITE_TOKEN}" >> "$GITHUB_ENV"
```

> 📖 Referencia: [GitHub Docs — Copilot coding agent setup steps](https://docs.github.com/en/copilot/managing-copilot/managing-github-copilot-in-your-organization/customizing-copilot-coding-agent-with-mcp/configuring-copilot-coding-agent-setup-steps)

---

### Paso 4 — Verificar que el agente puede hacer push

La próxima vez que el agente necesite publicar el wiki, usará el token así:

```bash
git clone "https://x-access-token:${WIKI_WRITE_TOKEN}@github.com/CuevazaArt/Pecunator.wiki.git" /tmp/wiki
cp wiki/*.md /tmp/wiki/
cd /tmp/wiki
git add .
git commit -m "Sync wiki from main"
git push origin master
```

Con el token correcto, el push tendrá éxito en lugar del error 403.

---

## ⚡ Opción A — PAT clásico `repo` *(más rápida)*

> Úsala si quieres empezar en 5 minutos sin preocuparte por la granularidad.  
> Limitación: el scope `repo` da acceso de escritura a **todos** tus repositorios privados, no sólo a Pecunator.

1. Ve a **[github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)**.
2. Pulsa **"Generate new token (classic)"**.
3. Marca el scope **`repo`** (incluye `repo:status`, `repo_deployment`, `public_repo`, `repo:invite`, `security_events`).
4. Copia el token y guárdalo como secret `WIKI_WRITE_TOKEN` igual que en la Opción B, Paso 2.
5. Agrega el mismo bloque en `.github/copilot-setup-steps.yml`.

---

## 🐢 Opción C — Sync manual desde el PR *(sin configuración)*

Si prefieres no crear tokens adicionales, el flujo es:

1. El agente escribe los archivos `.md` en `wiki/` dentro del branch del PR (como lo hace hoy).
2. Tú los copias al wiki manualmente en tu máquina:

```bash
# Clona el wiki una sola vez
git clone https://github.com/CuevazaArt/Pecunator.wiki.git

# Después de cada PR, copia los archivos
cp <ruta-a-PR>/wiki/*.md Pecunator.wiki/

# Publica
cd Pecunator.wiki
git add .
git commit -m "Sync wiki desde PR #X"
git push
```

O más rápido, directamente desde el editor web:  
`https://github.com/CuevazaArt/Pecunator/wiki/<Nombre-de-Pagina>/_edit`

---

## 🔒 Buenas prácticas de seguridad

| ✅ Hacer | ❌ Evitar |
|---------|---------|
| Usar fine-grained PAT con scope mínimo | PAT clásico con scope `admin` |
| Establecer expiración (90 días) | Tokens sin expiración |
| Guardar el token como Secret, no en código | Poner el token en `copilot-setup-steps.yml` en texto plano |
| Revocar el token si no está en uso | Dejar tokens activos indefinidamente |
| Rotar el token antes de su expiración | Olvidar la fecha de expiración |

> 📖 Ver también: **[Seguridad y Credenciales](Seguridad-y-Credenciales)** en este wiki.  
> 📖 NIST SP 800-57 (gestión de claves): [csrc.nist.gov](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)

---

## 🔍 Cómo verificar que el token está activo

```bash
# Desde tu terminal local, comprueba que el token tiene acceso
curl -H "Authorization: token <tu-token>" \
     https://api.github.com/repos/CuevazaArt/Pecunator \
     | python3 -m json.tool | grep '"permissions"' -A 10
```

Deberías ver `"push": true`. Si ves `"push": false` el token no tiene los permisos correctos.

---

## 📋 Checklist de implementación

```
□ Paso 1 — Creado fine-grained PAT con Contents: Read and Write
□ Paso 2 — PAT guardado como secret WIKI_WRITE_TOKEN en el repo
□ Paso 3 — .github/copilot-setup-steps.yml actualizado para exponer el secret
□ Paso 4 — Verificado con curl que el token tiene push: true
□ Recordatorio en calendario para rotar antes de la expiración
```

---

<div align="center">

**[⬆️ Inicio](Home)** · **[🔐 Seguridad y Credenciales](Seguridad-y-Credenciales)** · **[🛠️ Guía de Desarrollo](Guia-de-Desarrollo)**

<sub>📌 Esta guía sólo aplica al propietario del repositorio (<strong>CuevazaArt</strong>). Los tokens nunca deben compartirse.</sub>

</div>
