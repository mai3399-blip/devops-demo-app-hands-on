# אפליקציית ההדגמה: אותן תקלות, קודם ידנית ואז עם Kubernetes

מריצים את אפליקציית ההדגמה של הקורס, עם **שני** containers של `api-node` מאחורי ה־nginx של `client-react`. בודקים ארבעה דברים שקורים בכל מערכת אמיתית: גרסה חדשה, חזרה לגרסה קודמת בזהירות, עוד עותקים, ו־container שמת. כל הזמן רץ `probe.py`, ששולח 10 בקשות בשנייה ל־`/api/node/` וסופר כמה מהן נכשלו.

אחר כך עושים את אותם דברים ב־Kubernetes (kind), עם אותם images, ומשווים.

**איפה עובדים:** ב־Codespace, בתיקייה `demo-app-hands-on`. צריך שני טרמינלים: אחד לפקודות, ואחד ל־probe שרץ כל הזמן (Split terminal).

## הקוד של האפליקציה

הקוד של אפליקציית ההדגמה הוא של הקורס *Kubernetes: Beginner to Pro* של DevOps Directive, בתיקייה `06-demo-application`:

- ה־repo: https://github.com/sidpalas/devops-directive-kubernetes-course
- התיקייה, בגרסה שנבדקה: https://github.com/sidpalas/devops-directive-kubernetes-course/tree/3ea459f/06-demo-application
- הכול כקובץ zip: https://github.com/sidpalas/devops-directive-kubernetes-course/archive/3ea459f.zip

בתוך `demo-app-hands-on`:

```bash
git clone https://github.com/sidpalas/devops-directive-kubernetes-course course
cd course && git checkout 3ea459f && cd ..
APP=course/06-demo-application
```

## הקבצים

| קובץ | מה יש בו |
|---|---|
| `nginx/default.conf` | ה־nginx.conf של `client-react`, עם שינוי אחד: `/api/node/` הולך לרשימה של containers (upstream). זו הרשימה של ה־load balancer |
| `probe.py` | שולח 10 בקשות בשנייה, ומדפיס שורה בכל שנייה |
| `k8s/kind.yaml` | ‏cluster של שלושה nodes. פורט 30080 של ה־cluster הוא 8081 אצלכם |
| `k8s/demo-app.yaml` | אפליקציית ההדגמה ב־Kubernetes: ‏Secret, ‏Postgres, ה־migration, ושלושת החלקים |

איך לקרוא שורה של ה־probe:

```
21:25:34  ok  5  fail  5  hosts 1  HTTP502:5
21:25:36  ok 10  fail  0  hosts 2
```

בכל שנייה: כמה בקשות הצליחו (`ok`), כמה נכשלו (`fail`), מכמה containers של `api-node` הגיעו תשובות (`hosts`, רק בחלק א׳: ה־nginx שלנו כותב את זה ב־header), ולמה בקשות נכשלו (`HTTP502`, או `timeout`: בקשה שלקחה יותר משנייה).

## חלק א׳: ניהול ידני, עם Docker

### 0. images

שתי גרסאות של `api-node`: אותו קוד, שני images (ה־label שונה). כך אפשר לראות החלפת גרסה בלי לשנות את הקוד של הקורס.

```bash
docker build -t demo-app/api-node:0.1 --label version=0.1 $APP/api-node
docker build -t demo-app/api-node:0.2 --label version=0.2 $APP/api-node
docker build -t demo-app/api-golang:0.1 $APP/api-golang
docker build -t demo-app/client-react:0.1 $APP/client-react
docker build -t demo-app/db-migrator:0.1 $APP/postgresql
```

### 1. האפליקציה, עם שני api-node

```bash
docker network create demo-app
docker run -d --name db --network demo-app -e POSTGRES_PASSWORD=foobarbaz postgres:16.3-alpine
```

חכו ש־Postgres יעלה (`docker exec db pg_isready -U postgres` אומר `accepting connections`), ואז:

```bash
docker run --rm --network demo-app demo-app/db-migrator:0.1 -path=/app/migrations -database='postgres://postgres:foobarbaz@db:5432/postgres?sslmode=disable' up
docker run -d --name api-node-1 --network demo-app -e DATABASE_URL=postgres://postgres:foobarbaz@db:5432/postgres demo-app/api-node:0.1
docker run -d --name api-node-2 --network demo-app -e DATABASE_URL=postgres://postgres:foobarbaz@db:5432/postgres demo-app/api-node:0.1
docker run -d --name api-golang --network demo-app -e DATABASE_URL=postgres://postgres:foobarbaz@db:5432/postgres demo-app/api-golang:0.1
docker run -d --name client-react --network demo-app -p 8080:8080 -v "$PWD/nginx:/etc/nginx/conf.d:ro" demo-app/client-react:0.1
```

בטרמינל השני:

```bash
python3 probe.py http://localhost:8080/api/node/
```

צריך לראות `ok 10  fail 0  hosts 2` בכל שורה.

### 2. גרסה 0.2, בדרך הקצרה

**לפני שמריצים:** כמה בקשות ייכשלו?

```bash
docker rm -f api-node-1 api-node-2
docker run -d --name api-node-1 --network demo-app -e DATABASE_URL=postgres://postgres:foobarbaz@db:5432/postgres demo-app/api-node:0.2
docker run -d --name api-node-2 --network demo-app -e DATABASE_URL=postgres://postgres:foobarbaz@db:5432/postgres demo-app/api-node:0.2
```

**מה יצא אצלכם:** כמה בקשות נכשלו? ____

### 3. חזרה ל־0.1, בלי להפיל אף בקשה

המטרה: `fail 0` לאורך כל הדרך. מותר להשתמש ב־`docker run` (בשמות `api-node-3`, `api-node-4`), בעריכה של `nginx/default.conf`, ב־`docker exec client-react nginx -s reload` וב־`docker rm -f`. חשבו על הסדר לפני שמתחילים.

בדיקה שה־container החדש כבר עונה, מתוך ה־nginx:

```bash
docker exec client-react wget -qO- http://api-node-3:3000/ping
```

**מה יצא אצלכם:** כמה פקודות הקלדתם? ____ כמה בקשות נכשלו? ____

### 4. עוד שני עותקים

```bash
docker run -d --name api-node-5 --network demo-app -e DATABASE_URL=postgres://postgres:foobarbaz@db:5432/postgres demo-app/api-node:0.1
docker run -d --name api-node-6 --network demo-app -e DATABASE_URL=postgres://postgres:foobarbaz@db:5432/postgres demo-app/api-node:0.1
```

חכו עשר שניות. כמה `hosts` ה־probe מראה? עכשיו הוסיפו את שניהם ל־`nginx/default.conf`, ועשו `nginx -s reload`. כמה עכשיו?

### 5. container מת, ואף אחד לא אמר ל־nginx

```bash
docker kill api-node-5
```

אל תיגעו ב־nginx. **מה רואים ב־probe במשך 20 השניות הבאות?** ____

בסוף חלק א׳ מנקים, כדי לפנות את port 8080:

```bash
docker rm -f client-react api-golang db api-node-3 api-node-4 api-node-5 api-node-6
docker network rm demo-app
```

## חלק ב׳: אותו דבר עם Kubernetes (kind)

### 0. kind ו־kubectl, ‏cluster ו־images

פעם אחת ב־Codespace: ‏kind (‏Kubernetes שכל node שלו הוא container של Docker) ו־kubectl (הכלי שמדבר עם ה־cluster).

```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.33.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind
kubectl version --client
```

אם `kubectl` לא נמצא:

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl
```

ה־cluster, וה־images מחלק א׳:

```bash
kind create cluster --name demo --config k8s/kind.yaml
kind load docker-image demo-app/api-node:0.1 demo-app/api-node:0.2 demo-app/api-golang:0.1 demo-app/client-react:0.1 demo-app/db-migrator:0.1 --name demo
```

את `postgres:16.3-alpine` ה־nodes מושכים לבד מ־Docker Hub.

### 1. האפליקציה

```bash
kubectl apply -f k8s/demo-app.yaml
kubectl wait --for=condition=complete job/db-migrator --timeout=180s
kubectl rollout status deployment/api-node
kubectl get pods -o wide
```

בטרמינל השני:

```bash
python3 probe.py http://localhost:8081/api/node/
```

### 2. גרסה 0.2

ב־`k8s/demo-app.yaml`, ב־Deployment של `api-node`: מחליפים `image: demo-app/api-node:0.1` ב־`image: demo-app/api-node:0.2`, ואז:

```bash
kubectl apply -f k8s/demo-app.yaml
kubectl rollout status deployment/api-node
```

**כמה בקשות נכשלו?** ____ ראו את השגיאות ב־probe: ‏`HTTP502`. מאיפה הן?

### 3. ‏preStop: לחכות לפני SIGTERM

‏`api-node` סוגר את ה־port ברגע שהוא מקבל SIGTERM, אבל ה־Service עוד שולח אליו בקשות שנייה או שתיים. ב־`k8s/demo-app.yaml` יש ארבע שורות עם `#` מתחת ל־`readinessProbe` של `api-node`: מוחקים את ה־`#` מהן (`lifecycle`, ‏`preStop`: מחכים 5 שניות לפני ה־SIGTERM). את ה־image לא משנים. ואז `kubectl apply`.

**כמה בקשות נכשלו הפעם?** ____ שימו לב: גם זה rollout. ל־pods שמוחלפים עכשיו אין עוד את ה־preStop.

### 4. חזרה ל־0.1

מחזירים את ה־image ל־`demo-app/api-node:0.1`, ו־`kubectl apply`. עכשיו לכל ה־pods יש preStop.

**כמה בקשות נכשלו?** ____ כמה פקודות?

### 5. ארבעה עותקים

`replicas: 2` הופך ל־`replicas: 4` ב־Deployment של `api-node`, ו־`kubectl apply`. מתי הם מקבלים בקשות?

### 6. worker שלם מת

ב־`demo-worker2` רצים רק עותקים של `api-node` (ה־database וה־nginx על `demo-worker`, בגלל `nodeSelector`).

```bash
docker kill demo-worker2
kubectl get nodes
kubectl get pods -o wide
```

**כמה זמן עד ש־node מסומן `NotReady`? כמה זמן עד שיש שוב ארבעה pods מוכנים?** ____

בסוף:

```bash
kind delete cluster --name demo
```

## שאלות

1. בחלק א׳, מי זכר את הסדר בצעד 3? ובחלק ב׳?
2. למה צעד 3 של חלק ב׳ עוד הפיל בקשות, וצעד 4 לא?
3. בצעד 5 של חלק א׳, nginx המשיך לשלוח ל־container מת. מה ב־`k8s/demo-app.yaml` גורם ל־Kubernetes להפסיק לשלוח אליו?
4. ב־`k8s/demo-app.yaml`, ‏`DATABASE_URL` כתוב `db:5432`, כמו ב־Docker. למה זה עובד, אם אין container בשם `db`?
