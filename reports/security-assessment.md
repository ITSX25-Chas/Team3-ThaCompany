# Säkerhetsgranskning av company-website

**Senast uppdaterad:** 2026-11-03
**Omfattning:** Flask-applikation, beroenden, container, Kubernetes, GitHub Actions och körande labbmiljö

## Sammanfattning

De tidigare applikationsfynden SQL-injektion, IDOR, SSTI, förutsägbar Flask-nyckel och saknat CSRF-skydd är åtgärdade. Den aktuella Python-koden klarar 22 tester. `pip-audit` och Bandit gav inga kända beroende- eller Python-kodfynd den 3 november.

De största kvarvarande riskerna finns i leverans- och driftkedjan. `main` skyddas nu av ett aktivt ruleset med PR-krav, en godkännande granskare och testkontrollen `tests`. Deployment-workflowen har samtidigt tillgång till Headscale, Kubernetes och GitHub Container Registry. Kubernetes använder dessutom en långlivad deploy-token. Deployrollen har begränsats från pod- och bred secret-hantering till de resurser och verb som den normala deploymenten behöver, men den långlivade autentiseringen återstår att ersätta.

SBOM-scannern verifierar attesteringen mot GitHub OIDC och Trivy-versionen är låst. Installationsskriptet hämtas fortfarande vid körning och bör ersättas av en egen signerad scannerimage. Applikationscontainern kör som UID 10001, utan Kubernetes-token, med `RuntimeDefault` seccomp, nekad privilege escalation och alla capabilities borttagna. Resursgränser och NetworkPolicy har lagts till i examinationsuppdateringen.

Organisationsflytten har också följts upp. Imageadressen, Cosign-identiteten, scannerfallbacken och README pekar nu på `ITSX25-Chas/Team3-ThaCompany`. GitHub Actions är låsta till fullständiga commit-SHA:n. En ny deploy måste fortfarande köras för att verifiera hela kedjan i den nya organisationen.

## Genomförd verifiering

Granskningen utfördes mot senaste `main` och den auktoriserade Team 3-labbmiljön.

| Kontroll | Resultat |
|---|---|
| Pytest | 22 tester godkända |
| pip-audit | Inga kända sårbara Python-beroenden |
| Bandit | Inga Python-kodfynd |
| Semgrep | 0 fynd från 208 regler |
| Checkov | Den äldre kontrollen gav 42 Kubernetes-/containerfynd; relevanta fynd har omvärderats nedan |
| Dependabot | Kunde inte verifieras med aktuell API-behörighet |
| Branch protection | Aktivt ruleset på `main`: PR, en granskare, `tests`, inget force-push/radering |
| Containerkonfiguration | UID 10001, token avstängd, seccomp och drop ALL; måste återverifieras efter deploy |
| Sessionscookie | `HttpOnly` och `SameSite=Lax`, men saknar `Secure` |

Inga produktionsuppgifter, databasinnehåll eller secrets ändrades under verifieringen.

### Omprövning av containerfynd 3 november

En ny image byggdes från aktuell Debian-basimage och skannades med Trivy `0.75.0`. Resultatet var 44 High-paketträffar, motsvarande nio unika CVE:er, och inga Critical. Åtta tidigare accepterade CVE:er saknar fortfarande fix i Debian Trixie. Ett nytt fynd, CVE-2026-119373 i `libsqlite3-0`, gäller en FTS5-kodväg. Applikationen skapar inga FTS5-tabeller och exponerar inte användarstyrd SQL, så kodvägen är inte verifierat nåbar.

De nio exakta undantagen förlängdes därför tidsbegränsat till den 20 november 2026. Undantagen minskar endast larmbrus; de tar inte bort sårbarheterna. Full scannerutdata behålls och alla andra High/Critical-fynd fortsätter att ge rött larm.

## Tidigare registrerade säkerhetsärenden

| Issue | Fynd | Aktuell status |
|---|---|---|
| [#1](https://github.com/ITSX25-Chas/Team3-ThaCompany/issues/1) | SQL-injektion i inloggningen | Åtgärdad med parametriserad fråga och lösenordskontroll |
| [#2](https://github.com/ITSX25-Chas/Team3-ThaCompany/issues/2) | IDOR för användarprofiler | Åtgärdad med ägarskapskontroll |
| [#3](https://github.com/ITSX25-Chas/Team3-ThaCompany/issues/3) | CTF-flagga i Git-historik | Issue stängd; objektet finns kvar i nåbar historik |
| [#4](https://github.com/ITSX25-Chas/Team3-ThaCompany/issues/4) | CTF-flagga på remote-branch | Åtgärdad; den berörda remote-branchen finns inte längre |
| [#16](https://github.com/ITSX25-Chas/Team3-ThaCompany/issues/16) | Förutsägbar Flask `SECRET_KEY` | Åtgärdad med GitHub- och Kubernetes-secret |
| [#17](https://github.com/ITSX25-Chas/Team3-ThaCompany/issues/17) | Saknat CSRF-skydd | Åtgärdad med Flask-WTF och CSRF-token |

Historiska CTF-flaggor ska betraktas som övningsdata. Om samma metod någon gång exponerar en riktig hemlighet måste hemligheten roteras även om Git-historiken senare rensas.

## Kvarvarande fynd

### Fynd 1: Branchskydd och långlivad Kubernetes-token

**Allvarlighetsgrad:** Hög
**Berörda filer:** `.github/workflows/deploy.yml`, `k8s/github-permissions.yaml`, `scripts/generate-kubeconfig.sh`
**Status:** Delvis åtgärdad 2026-11-03

En push till `main` startar deployment-workflowen och workflowen får tillgång till `HEADSCALE_API_KEY`, `KUBECONFIG`, `APP_SECRET_KEY`, GHCR och GitHub OIDC. Ett aktivt ruleset kräver nu PR, en godkännande granskare och testkontrollen `tests` samt blockerar force-push och radering.

Kubeconfig-filen använder en manuellt skapad `kubernetes.io/service-account-token`. Den körande tokenen skapades 2026-09-21 och är fortfarande giltig. Följande behörigheter verifierades för `github-deployer` i `default`-namespace:

```text
get secrets:    yes
delete secrets: yes
create pods:    yes
```

Rollen har därefter begränsats: pod- och eventbehörigheter har tagits bort och secret-behörigheten omfattar inte längre `list`, `watch` eller `delete`. Den permanenta service-account-tokenen är fortfarande en kvarstående risk.

**Rekommenderad åtgärd:**

- Aktivera branch protection med obligatorisk PR, godkända tester och granskare.
- Använd ett GitHub Environment med godkännande för deployment.
- Ersätt den permanenta Kubernetes-tokenen med kortlivad autentisering.
- Ta bort `list`, `watch` och `delete` för secrets och övriga verbs som deploymenten inte behöver.
- Förkonfigurera applikationssecreten utanför den vanliga deployrollen.

### Fynd 2: SBOM-scannern kör extern kod från en rörlig branch

**Allvarlighetsgrad:** Hög
**Berörd fil:** `k8s/sbom-scanner/scanner-cronjob.yaml`
**Status:** Delvis åtgärdad

CronJoben installerar en bestämd Trivy-version från en versionstagg vid varje körning. Det är bättre än en rörlig `main`-branch men saknar fortfarande checksummeverifiering:

```bash
curl https://raw.githubusercontent.com/aquasecurity/trivy/v${TRIVY_VERSION}/contrib/install.sh | sh
```

Innehållet i den externa `main`-branchen kan förändras utan någon ändring i Team 3-repot. Ett komprometterat upstream-repo eller installationsskript ger kodkörning i scanner-podden. Podden kör som root och får Discord-webhooken som miljövariabel.

**Rekommenderad åtgärd:** Bygg en egen scanner-image med bestämda versioner av Trivy, Cosign, curl och jq. Signera imagen och referera till den med digest.

### Fynd 3: Sårbarhetskontrollen sker efter deployment

**Allvarlighetsgrad:** Hög
**Berörda filer:** `.github/workflows/deploy.yml`, `k8s/sbom-scanner/scanner-cronjob.yaml`
**Status:** Öppen

Deploy-workflowen bygger, signerar och driftsätter imagen. CronJoben skannar den körande imagen senare enligt ett dagligt schema. En image med en känd High/Critical-sårbarhet kan därför vara aktiv fram till nästa lyckade scannerkörning. Om CronJoben misslyckas skickas inget särskilt driftlarm till Discord.

**Rekommenderad åtgärd:** Kör Trivy mot imagen eller den genererade SBOM-filen i CI och stoppa deployment vid överenskommen nivå. Behåll CronJoben för återkommande kontroll och lägg till larm för misslyckade scannerjobb.

### Fynd 4: SBOM-attesteringens identitet

**Allvarlighetsgrad:** Medel
**Berörd fil:** `k8s/sbom-scanner/scanner-cronjob.yaml`
**Status:** Åtgärdad i kod; ny organisationsidentitet måste driftverifieras

Scannern använder `cosign verify-attestation` med GitHubs OIDC-issuer och exakt workflow-identitet. Identiteten har uppdaterats till den nya organisationen. Nästa deploy och scannerjobb ska bekräfta att image, attestering och verifieringsregel överensstämmer.

**Rekommenderad åtgärd:** Använd `cosign verify-attestation` med GitHubs OIDC issuer och den exakta workflow-identiteten. Skanna endast predicate-data från en godkänd verifiering.

### Fynd 5: Containerbehörigheter

**Allvarlighetsgrad:** Medel
**Berörda filer:** `Dockerfile`, `k8s/deployment.yaml`
**Status:** Åtgärdad

Utgångsläget var root och monterad service-account-token. Deploymenten har därefter härdats med:

```text
runAsUser: 10001
automountServiceAccountToken: false
allowPrivilegeEscalation: false
capabilities.drop: ["ALL"]
seccompProfile.type: RuntimeDefault
```

Applikationen behöver inte Kubernetes API. Default-kontot har begränsad åtkomst, men tokenen ger API-discovery och ökar angreppsytan. Deploymenten saknar även seccomp-profil, capability-begränsning, skydd mot privilege escalation och resursgränser.

**Rekommenderad åtgärd:**

```yaml
spec:
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: web
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
```

Skapa dessutom en användare med högt UID i Docker-imagen och ange CPU-/minnesgränser.

### Fynd 6: Okrypterad HTTP och sessionscookie utan Secure

**Allvarlighetsgrad:** Medel
**Berörda filer:** `k8s/ingress.yaml`, `k8s/deployment.yaml`, `src/company_website/config.py`
**Status:** Öppen

Applikationen exponeras via HTTP. Live-svaret satte sessionscookien med `HttpOnly` och `SameSite=Lax`, men utan attributet `Secure`. Deploymenten sätter uttryckligen `SESSION_COOKIE_SECURE=false`.

**Rekommenderad åtgärd:** Aktivera TLS på ingressen och sätt `SESSION_COOKIE_SECURE=true`. Lägg även till HSTS när all åtkomst använder HTTPS.

### Fynd 7: NetworkPolicy och resursgränser

**Allvarlighetsgrad:** Medel
**Berörda filer:** `k8s/deployment.yaml`, saknad NetworkPolicy
**Status:** Åtgärdad i kod; driftverifiering återstår

En NetworkPolicy begränsar nu inkommande trafik till ingress-nginx och utgående trafik till klustrets DNS. Deploymenten har CPU- och minnesgränser. Kontrollera efter deployment att k3s nätverkspolicy faktiskt verkställs och att health checks fungerar.

**Rekommenderad åtgärd:** Inför default-deny i applikationens namespace och tillåt endast trafik från ingress-nginx samt dokumenterad utgående trafik. Ange rimliga CPU- och minnesgränser.

### Fynd 8: GitHub Actions låsta till commit-SHA

**Allvarlighetsgrad:** Medel
**Berörda filer:** `.github/workflows/deploy.yml`, `.github/workflows/tests.yml`
**Status:** Åtgärdad i kod

Externa Actions är nu låsta till fullständiga commit-SHA:n med versionskommentarer. Repositoryinställningen bör dessutom begränsa vilka Actions som får användas.

**Rekommenderad åtgärd:** Lås varje extern Action till fullständig commit-SHA och använd Dependabot för kontrollerade uppdateringar. Begränsa tillåtna Actions i repository-inställningarna.

### Fynd 9: Inloggningen saknar rate limiting och använder delat labbkonto

**Allvarlighetsgrad:** Låg/medel
**Berörd kod:** `src/company_website/auth.py`
**Status:** Öppen

Inloggningen saknar begränsning av upprepade försök. Det dokumenterade kontot `dev` delas av flera användare, vilket försämrar spårbarheten. I den nuvarande Tailnet-avgränsade labbmiljön är risken lägre än för en publik tjänst.

**Rekommenderad åtgärd:** Skapa personliga konton, inför rate limiting och logga misslyckade inloggningsförsök utan att logga lösenord.

### Fynd 10: Säkerhetsheaders saknas

**Allvarlighetsgrad:** Låg
**Berörda komponenter:** Flask och ingress-nginx
**Status:** Åtgärdad i kod; verifieras efter deployment

Applikationen sätter nu Content Security Policy, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` och `Permissions-Policy`. HSTS införs först när all åtkomst sker över HTTPS.

**Rekommenderad åtgärd:** Sätt en anpassad CSP och övriga headers i ingress-nginx eller med Flask-Talisman. Verifiera att CSP:n tillåter applikationens befintliga CSS och JavaScript innan den görs blockerande.

## Prioriterad åtgärdsordning

1. Kör och verifiera pipeline, Cosign och scanner efter organisationsflytten.
2. Ersätt den långlivade Kubernetes-tokenen och överväg deployment-godkännande via GitHub Environment.
3. Bygg en egen checksummeverifierad och signerad scannerimage.
4. Inför TLS och sätt `SESSION_COOKIE_SECURE=true`.
5. Verifiera NetworkPolicy och resursgränser i det körande klustret.
6. Inför rate limiting och personliga applikationskonton.

## Avgränsning för framtida pentestmiljö

Om en sårbar och en patchad version ska köras parallellt bör de använda separata namespaces, databaser, service accounts och hostnames. Den sårbara versionen ska endast innehålla avsiktliga applikationssårbarheter. Infrastrukturens secrets, Kubernetes API och molnidentiteter ska inte vara åtkomliga från pentestcontainern.
