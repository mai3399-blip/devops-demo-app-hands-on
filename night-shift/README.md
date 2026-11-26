# משמרת לילה: קודם ידנית, ואז עם Kubernetes

מריצים שירות קטן (`shop`) בשני containers מאחורי nginx, ובודקים שלושה דברים שקורים בכל מערכת אמיתית: מחליפים גרסה, מוסיפים עותקים, ו־container מת. כל הזמן רץ `probe.py`, ששולח 10 בקשות בשנייה וסופר כמה מהן נכשלו.

אחר כך עושים את אותם שלושה דברים ב־Kubernetes (kind), ומשווים.

**איפה עובדים:** ב־Codespace, בתיקייה `night-shift`. צריך שני טרמינלים: אחד לפקודות, ואחד ל־probe שרץ כל הזמן (Split terminal).

## הקבצים

| קובץ | מה יש בו |
|---|---|
| `app/app.py`, `app/Dockerfile` | השירות. עולה במשך 3 שניות (כמו שירות שמתחבר קודם לבסיס הנתונים), ועונה ב־JSON עם הגרסה ושם ה־container |
| `lb/shop.conf` | ההגדרה של nginx: רשימת ה־containers שמקבלים בקשות (upstream) |
| `probe.py` | שולח 10 בקשות בשנייה, ומדפיס שורה בכל שנייה |
| `k8s/kind.yaml` | ‏cluster של שלושה nodes. פורט 30080 של ה־cluster הוא 8081 אצלכם |
| `k8s/shop.yaml` | ‏Deployment של 2 עותקים, ו־Service |

איך לקרוא שורה של ה־probe:

```
13:30:23  ok  0  fail 10  HTTP502:10
13:30:27  ok 10  fail  0  v2:10  hosts 2
```

בכל שנייה: כמה בקשות הצליחו (`ok`), כמה נכשלו (`fail`), איזו גרסה ענתה (`v2:10`), מכמה containers שונים הגיעו תשובות (`hosts 2`), ולמה בקשות נכשלו (`HTTP502` או `timeout`, כלומר בקשה שלקחה יותר משנייה).

## חלק א׳: ניהול ידני, עם Docker ו־nginx

### 0. הכנה

```bash
docker build -t shop:1 --build-arg VERSION=1 app
docker build -t shop:2 --build-arg VERSION=2 app
docker network create shop-net
docker run -d --name shop-1 --network shop-net shop:1
docker run -d --name shop-2 --network shop-net shop:1
```

חכו שניים־שלוש שניות (`docker logs shop-1` צריך להראות `listening`), ורק אז:

```bash
docker run -d --name lb --network shop-net -p 8080:8080 -v "$PWD/lb:/etc/nginx/conf.d:ro" nginx:1.27-alpine
```

בטרמינל השני:

```bash
python3 probe.py http://localhost:8080
```

צריך לראות `ok 10  fail 0` בכל שורה.

### 1. גרסה חדשה, בדרך הקצרה

**לפני שמריצים:** כמה בקשות ייכשלו?

```bash
docker rm -f shop-1 shop-2
docker run -d --name shop-1 --network shop-net shop:2
docker run -d --name shop-2 --network shop-net shop:2
```

**מה יצא אצלכם:** כמה שניות היו עם `ok 0`? ____

### 2. חזרה ל־v1, בלי להפיל אף בקשה

המטרה: `fail 0` לאורך כל הדרך. מותר להשתמש ב־`docker run`, בעריכה של `lb/shop.conf`, ב־`docker exec lb nginx -s reload` וב־`docker rm -f`. חשבו על הסדר לפני שמתחילים.

בדיקה שה־container החדש כבר עונה, מתוך ה־lb:

```bash
docker exec lb wget -qO- http://shop-3:8000/health
```

**מה יצא אצלכם:** כמה פקודות הקלדתם? ____ כמה בקשות נכשלו? ____

### 3. עוד שני עותקים

```bash
docker run -d --name shop-5 --network shop-net shop:1
docker run -d --name shop-6 --network shop-net shop:1
```

**לפני שממשיכים:** מה ה־probe מראה ב־`hosts`? למה?

עכשיו הוסיפו את `shop-5` ו־`shop-6` ל־`lb/shop.conf`, והריצו `docker exec lb nginx -s reload`. מה השתנה ב־`hosts`?

### 4. ‏container מת, ואף אחד לא מעדכן את nginx

```bash
docker kill shop-5
```

הסתכלו על ה־probe 20 שניות. ואז:

```bash
docker logs lb 2>&1 | tail -3
```

**מה יצא אצלכם:** האם הכישלונות נגמרו לבד? ____ מה צריך לעשות כדי שייגמרו?

### ניקוי של חלק א׳

עצרו את ה־probe (Ctrl-C) ורשמו את השורה `sent ..., failed ...` שהוא מדפיס. ואז:

```bash
docker rm -f lb shop-1 shop-2 shop-3 shop-4 shop-5 shop-6
docker network rm shop-net
```

## חלק ב׳: אותו דבר, עם Kubernetes

### 0. הכנה

ב־Codespace אין kind מראש: מתקינים אותו כמו בצעד 0 של חלק ב׳ ב־`demo-app-hands-on/README.md`. מי שעשה את חלק ב׳ בכיתה באותו Codespace כבר התקין אותו.

```bash
kind create cluster --name shop --config k8s/kind.yaml
kind load docker-image shop:1 shop:2 --name shop
kubectl apply -f k8s/shop.yaml
kubectl rollout status deployment/shop
kubectl get pods -o wide
```

בטרמינל השני:

```bash
python3 probe.py http://localhost:8081
```

אם ה־Codespace איטי מאוד עם שלושה nodes: `kind create cluster --name shop` בלי `--config`, ו־probe מול `kubectl port-forward service/shop 8081:80`. בלי worker נוסף, את שלב 4 אי אפשר לעשות.

### 1. גרסה חדשה

ב־`k8s/shop.yaml` שנו `image: shop:1` ל־`image: shop:2`, ואז:

```bash
kubectl apply -f k8s/shop.yaml
kubectl rollout status deployment/shop
```

**לפני שמריצים:** כמה בקשות ייכשלו? **מה יצא אצלכם:** ____

### 2. חזרה ל־v1

אותה עריכה, הפוכה, ו־`kubectl apply`. **מה יצא אצלכם:** ____

### 3. ארבעה עותקים

ב־`k8s/shop.yaml` שנו `replicas: 2` ל־`replicas: 4`, ו־`kubectl apply`. מה קרה ל־`hosts` ב־probe? נגעתם ב־Service?

### 4. ‏node שלם מת

```bash
kubectl get pods -o wide
docker kill shop-worker2
kubectl get nodes -w
```

ב־kind כל node הוא container, ו־`docker kill` הוא ניתוק חשמל. הסתכלו על ה־probe ועל `kubectl get pods -o wide` כל כמה שניות.

**מה יצא אצלכם:** אחרי כמה שניות ה־node הפך ל־`NotReady`? ____ אחרי כמה שניות היו שוב ארבעה pods ב־`Running`? ____ מתי הפסיקו הכישלונות ב־probe? ____

### ניקוי

```bash
kind delete cluster --name shop
```

## הסיכום שלכם

| מה קרה | ניהול ידני: בקשות שנכשלו | ניהול ידני: פקודות | Kubernetes: בקשות שנכשלו | Kubernetes: פקודות |
|---|---|---|---|---|
| גרסה חדשה | | | | |
| חזרה לגרסה קודמת | | | | |
| עוד עותקים | | | | |
| ‏container או node מת | | | | |

ושאלה אחת: בכל השורות, גם בניהול ידני אפשר להגיע לאפס כישלונות. אז מה בדיוק Kubernetes חוסך?
