import { initializeApp } from "https://www.gstatic.com/firebasejs/13.2.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, onAuthStateChanged, signInWithPopup, signOut } from "https://www.gstatic.com/firebasejs/13.2.0/firebase-auth.js";
import { getFirestore, collection, doc, getDoc, limit, onSnapshot, orderBy, query, serverTimestamp, setDoc, writeBatch } from "https://www.gstatic.com/firebasejs/13.2.0/firebase-firestore.js";
import { firebaseConfig } from "./firebase_config.js";

const $ = (selector) => document.querySelector(selector);
const won = (value) => `₩${Math.trunc(value).toLocaleString("ko-KR")}`;
const names = ["삼성전자", "애플", "테슬라", "아마존", "로블록스", "SK하이닉스", "대한항공", "코스트코", "코카콜라", "한국전력"];
const initialPrices = [270500, 445969, 668437, 395650, 64184, 1819000, 26050, 1571201, 121058, 38750];
const ranges = [[-2,2],[-3,3],[-12,12],[-5,5],[-15,15],[-7,7],[-6,6],[-2,2],[-1,1],[-4,4]];
const headlines = [
  [["갤럭시 신제품 사전 예약 판매 호조","차세대 메모리 공급 계약 확대","AI 반도체 수요 증가에 실적 기대감"],["메모리 가격 약세에 수익성 우려","신제품 출시 일정 조정 가능성 제기","반도체 업황 둔화 전망에 투자심리 위축"]],
  [["신형 아이폰 공개 후 초기 판매 호조","서비스 부문 매출 성장세 지속","차세대 기기 공급망 확대"],["주요 시장 스마트폰 판매 둔화","앱스토어 규제 강화 가능성 부각","신제품 생산 비용 증가 우려"]],
  [["신형 전기차 주문량 예상치 상회","자율주행 기능 업데이트 공개","배터리 생산 효율 개선 발표"],["전기차 가격 인하로 수익성 우려","신차 출시 일정 지연 가능성","주요 시장 판매량 감소 전망"]],
  [["클라우드 사업 성장에 실적 기대","물류 자동화 투자 확대 발표","신규 AI 서비스 이용 증가"],["물류 비용 증가로 마진 부담","클라우드 시장 경쟁 심화","대형 투자 계획에 비용 우려"]],
  [["신규 게임 동시 접속자 기록 경신","인기 콘텐츠 업데이트 호평","해외 이용자 증가세 확인"],["일부 지역 이용자 성장 둔화","신작 출시 일정 변경","콘텐츠 운영 비용 증가 우려"]],
  [["고대역폭 메모리 공급 확대 기대","AI 서버용 메모리 수요 급증","차세대 메모리 양산 계획 발표"],["메모리 가격 조정 가능성 제기","생산 설비 투자 부담 확대","주요 고객사 재고 조정 소식"]],
  [["국제선 여객 수요 회복세 지속","신규 노선 취항으로 예약 증가 기대","화물 사업 매출 증가세 확인"],["항공유 가격 상승으로 비용 부담","운임 경쟁 심화에 수익성 우려","일부 노선 운항 조정 발표"]],
  [["회원 갱신율 상승으로 매출 기대","온라인 주문 증가세 확인","신규 점포 출점 계획 공개"],["소비 둔화로 객단가 하락 우려","인건비와 물류비 부담 확대","일부 상품 가격 인하 검토"]],
  [["신규 음료 제품 출시 계획 발표","해외 시장 판매량 증가","원재료 비용 안정으로 수익 개선 기대"],["주요 원재료 가격 상승 우려","일부 시장 판매 감소","환율 변동에 비용 부담 확대"]],
  [["전력 수요 증가로 판매량 확대 기대","연료비 안정에 실적 개선 전망","전력망 투자 계획 발표"],["연료비 상승에 비용 부담","전력 요금 조정 지연 우려","설비 정비 비용 증가 전망"]]
];

const game = {
  cash: 5000000, holdings: Array(10).fill(0), cost: Array(10).fill(0), realized: Array(10).fill(0),
  prices: [...initialPrices], history: initialPrices.map((n) => [n]), selected: 0,
  trendDirection: Array(10).fill(0), trendRemaining: Array(10).fill(0), trendDuration: Array(10).fill(0), trendStrength: Array(10).fill(0),
  bubbleRemaining: Array(10).fill(0), latestNewsType: Array(10).fill("-"), news: Array.from({length:10}, () => []),
  bestScore: 5000000, bestTime: new Date(), currentUser: null, nickname: "", title: "", isCurrentLeader: false, timer: null, messageTimer: null
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const configReady = !Object.values(firebaseConfig).some((value) => !value || String(value).includes("YOUR_"));
const developerEmail = "booster12045@gmail.com";
let rankingUnsubscribe = null;
let profileLeaderUnsubscribe = null;

function showView(view) {
  ["authView", "gameView", "rankingView", "profileView"].forEach((id) => $(`#${id}`).classList.toggle("hidden", id !== view));
  if (view !== "rankingView" && rankingUnsubscribe) { rankingUnsubscribe(); rankingUnsubscribe = null; }
  if (view !== "profileView" && profileLeaderUnsubscribe) { profileLeaderUnsubscribe(); profileLeaderUnsubscribe = null; }
  if (game.timer) clearInterval(game.timer);
  game.timer = view === "gameView" ? setInterval(tickMarket, 1000) : null;
}

function isDeveloperAccount() {
  return game.currentUser?.email?.toLowerCase() === developerEmail;
}

function addTitleBadge(container, title) {
  const badge = document.createElement("span");
  badge.className = `title-badge ${title === "개발자" ? "title-badge-developer" : "title-badge-king"}`;
  badge.textContent = title;
  container.append(badge);
}

function renderProfileTitles() {
  const badges = $("#profileTitleBadges");
  badges.replaceChildren();
  if (isDeveloperAccount() && game.title === "개발자") addTitleBadge(badges, "개발자");
  if (game.isCurrentLeader) addTitleBadge(badges, "익절왕");
  if (!badges.childElementCount) {
    const empty = document.createElement("span");
    empty.className = "profile-no-title";
    empty.textContent = "현재 표시 중인 칭호가 없습니다.";
    badges.append(empty);
  }
  $("#developerTitleControl").classList.toggle("hidden", !isDeveloperAccount());
  $("#profileTitleSelect").value = isDeveloperAccount() ? game.title : "";
  $("#profileTitleHint").textContent = isDeveloperAccount()
    ? "‘개발자’는 이 계정에서 설정할 수 있고, ‘익절왕’은 현재 랭킹 1위에게 자동으로 표시됩니다."
    : "‘개발자’는 지정된 계정만 설정할 수 있습니다. ‘익절왕’은 현재 랭킹 1위에게 자동 표시되고 순위가 바뀌면 함께 이동합니다.";
}

function setMessage(message, kind = "") {
  const node = $("#gameMessage");
  node.textContent = message;
  node.className = `message ${kind}`;
  clearTimeout(game.messageTimer);
  game.messageTimer = setTimeout(() => { node.textContent = ""; node.className = "message"; }, 4000);
}

function updateBestScore() {
  if (game.cash > game.bestScore) {
    game.bestScore = game.cash;
    game.bestTime = new Date();
  }
}

function formatLocalDate(date) {
  return new Intl.DateTimeFormat("ko-KR", {dateStyle:"medium",timeStyle:"medium"}).format(date);
}

function resetGame() {
  game.cash = 5000000;
  game.holdings = Array(10).fill(0); game.cost = Array(10).fill(0); game.realized = Array(10).fill(0);
  game.prices = [...initialPrices]; game.history = initialPrices.map((n) => [n]); game.selected = 0;
  game.trendDirection = Array(10).fill(0); game.trendRemaining = Array(10).fill(0); game.trendDuration = Array(10).fill(0); game.trendStrength = Array(10).fill(0);
  game.bubbleRemaining = Array(10).fill(0); game.latestNewsType = Array(10).fill("-"); game.news = Array.from({length:10}, () => []);
  game.lastPrices = [...initialPrices]; $("#quantityInput").value = "1";
  addNews(0, true, "갤럭시 신제품 공개 기대감에 관심 집중");
  addNews(5, true, "AI 메모리 수요 확대 전망");
  addNews(2, false, "전기차 가격 경쟁 심화 우려");
  game.bestScore = game.cash; game.bestTime = new Date();
  render(); setMessage("새 게임을 시작했습니다.", "positive");
}

function addNews(index, positive, headline, kind = null, duration = null) {
  const tag = kind || (positive ? "호재" : "악재");
  game.latestNewsType[index] = tag;
  game.news[index].unshift({time:new Date(), index, positive, headline, kind, duration});
  game.news[index] = game.news[index].slice(0, 5);
}

function durationForNews(headline) {
  const rules = [
    [["기록 경신","계약 확대","수요 급증","매출 성장","판매 호조","공급 확대"],[24,40]],
    [["비용 부담","경쟁 심화","규제 강화","재고 조정","판매 감소","수요 둔화"],[20,36]],
    [["출시","공개","업데이트","신규 노선","출점"],[14,26]],
    [["계획","기대","전망","호평"],[10,20]]
  ];
  const match = rules.find(([words]) => words.some((word) => headline.includes(word)));
  const [low, high] = match?.[1] || [12,25];
  return Math.floor(Math.random() * (high - low + 1)) + low;
}

function tickMarket() {
  game.prices.forEach((current, i) => {
    let price = current;
    let rate = (Math.floor(Math.random() * (ranges[i][1] - ranges[i][0] + 1)) + ranges[i][0]) / 100;
    if (game.bubbleRemaining[i] > 0) {
      price *= 1 + (Math.random() * .015 + .01);
      game.bubbleRemaining[i]--;
      if (game.bubbleRemaining[i] === 0) {
        price *= 1 - (Math.random() * .15 + .20);
        const duration = Math.floor(Math.random() * 9) + 8;
        addNews(i, false, "과열된 매수세가 식으며 버블 붕괴, 차익 실현 매물 출회", "버블", duration);
        game.trendDirection[i] = -1; game.trendRemaining[i] = duration; game.trendDuration[i] = duration;
        game.trendStrength[i] = Math.random() * .002 + .001;
      }
    } else {
      if (game.trendRemaining[i] > 0) {
        const strength = game.trendStrength[i];
        const phase = game.trendRemaining[i] / Math.max(1, game.trendDuration[i]);
        const fade = .55 + .45 * phase;
        rate += game.trendDirection[i] * strength * fade * (Math.random() * 1.1 + .35);
        rate += (Math.random() * 2 - 1) * strength * 1.5;
        game.trendRemaining[i]--;
        if (game.trendRemaining[i] === 0) { game.trendDirection[i] = 0; game.trendStrength[i] = 0; }
      }
      price *= 1 + rate;
      const chance = Math.random() * 100;
      if (chance <= 1.2) {
        price *= 1 + (Math.random() * .025 + .015);
        const headline = headlines[i][0][Math.floor(Math.random() * headlines[i][0].length)];
        const duration = durationForNews(headline); addNews(i, true, headline, null, duration);
        game.trendDirection[i] = 1; game.trendRemaining[i] = duration; game.trendDuration[i] = duration;
        game.trendStrength[i] = Math.random() * .0025 + .0015;
      } else if (chance >= 98.8) {
        price *= 1 - (Math.random() * .025 + .015);
        const headline = headlines[i][1][Math.floor(Math.random() * headlines[i][1].length)];
        const duration = durationForNews(headline); addNews(i, false, headline, null, duration);
        game.trendDirection[i] = -1; game.trendRemaining[i] = duration; game.trendDuration[i] = duration;
        game.trendStrength[i] = Math.random() * .0025 + .0015;
      }
      if (Math.random() < .0025) {
        price *= 1.02; game.bubbleRemaining[i] = Math.floor(Math.random() * 7) + 8;
        addNews(i, true, "테마 매수세 급증, 단기간 급등에 버블 우려 확산", "버블");
      }
    }
    const previous = game.prices[i];
    game.prices[i] = Math.max(10, Math.round(price));
    game.history[i].push(game.prices[i]);
    if (game.history[i].length > 100) game.history[i].shift();
    game.lastPrices ??= [...initialPrices];
    game.lastPrices[i] = previous;
  });
  render();
}

function totalAssets() { return game.cash + game.holdings.reduce((sum, qty, i) => sum + qty * game.prices[i], 0); }

function trade(buy) {
  const input = $("#quantityInput");
  const qty = Math.min(9999, Math.floor(Number(input.value)));
  if (!Number.isFinite(qty) || qty <= 0) { setMessage("주문 수량은 1주 이상이어야 합니다.", "negative"); return; }
  const i = game.selected; const amount = game.prices[i] * qty;
  if (buy) {
    if (amount > game.cash) { setMessage("매수할 수 없습니다.", "negative"); return; }
    game.cash -= amount; game.holdings[i] += qty; game.cost[i] += amount;
    setMessage(`${names[i]} ${qty.toLocaleString()}주를 매수했습니다.`, "positive");
  } else {
    if (qty > game.holdings[i]) { setMessage("보유 주식 수가 부족합니다.", "negative"); return; }
    const removedCost = game.cost[i] / game.holdings[i] * qty;
    game.holdings[i] -= qty; game.cost[i] -= removedCost; game.realized[i] += amount - removedCost;
    if (game.holdings[i] === 0) game.cost[i] = 0;
    game.cash += amount; setMessage(`${names[i]} ${qty.toLocaleString()}주를 매도했습니다.`, "positive");
  }
  updateBestScore(); render();
}

function render() {
  const total = totalAssets();
  $("#totalAssets").textContent = won(total);
  $("#bestScore").textContent = won(game.bestScore);
  $("#bestTime").textContent = formatLocalDate(game.bestTime);
  $("#recordTime").textContent = formatLocalDate(game.bestTime);
  $("#cashBalance").textContent = won(game.cash);
  const list = $("#stockList");
  list.replaceChildren(...names.map((name, i) => {
    const button = document.createElement("button"); button.type = "button";
    button.className = `stock-row${i === game.selected ? " active" : ""}`;
    const change = game.prices[i] >= (game.lastPrices?.[i] ?? initialPrices[i]);
    const type = game.latestNewsType[i];
    button.innerHTML = `<span class="stock-name"></span><span class="stock-price ${change ? "positive" : "negative"}"></span><span class="stock-news"></span><span class="stock-shares"></span>`;
    button.querySelector(".stock-name").textContent = name;
    button.querySelector(".stock-price").textContent = game.prices[i].toLocaleString("ko-KR");
    const news = button.querySelector(".stock-news"); news.textContent = type;
    const newsClass = type === "호재" ? "good" : type === "악재" ? "bad" : type === "버블" ? "bubble" : "";
    if (newsClass) news.classList.add(newsClass);
    button.querySelector(".stock-shares").textContent = `${game.holdings[i]}주`;
    button.addEventListener("click", () => { game.selected = i; render(); });
    return button;
  }));
  const i = game.selected, price = game.prices[i], values = game.history[i];
  const delta = values.at(-1) - values[0], pct = values[0] ? delta / values[0] * 100 : 0;
  $("#selectedName").textContent = names[i]; $("#selectedPrice").textContent = won(price);
  const changeEl = $("#priceChange"); changeEl.textContent = `${delta >= 0 ? "+" : ""}${Math.round(delta).toLocaleString()}원 (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)`;
  changeEl.className = delta >= 0 ? "positive" : "negative";
  $("#positionName").textContent = `${names[i]} 보유`; $("#positionShares").textContent = `${game.holdings[i].toLocaleString()}주`;
  const value = game.holdings[i] * price, unrealized = value - game.cost[i], unrealizedPct = game.cost[i] ? unrealized / game.cost[i] * 100 : 0;
  setMetric("#positionValue", won(value)); setMetric("#unrealizedProfit", `${unrealized > 0 ? "+" : ""}${Math.round(unrealized).toLocaleString()}원`, unrealized);
  $("#unrealizedPercent").textContent = `(${unrealizedPct >= 0 ? "+" : ""}${unrealizedPct.toFixed(1)}%)`;
  setMetric("#realizedProfit", `${game.realized[i] > 0 ? "+" : ""}${Math.round(game.realized[i]).toLocaleString()}원`, game.realized[i]);
  $("#newsTitle").textContent = `시장 뉴스 · ${names[i]}`;
  const newsRows = game.news[i].map((item) => {
    const row = document.createElement("div"); row.className = "news-row";
    const time = document.createElement("time"); time.textContent = item.time.toLocaleTimeString("ko-KR", {hour12:false});
    const tag = document.createElement("span"); tag.className = `news-tag${item.kind === "버블" ? " bubble" : item.positive ? "" : " bad"}`; tag.textContent = item.kind || (item.positive ? "호재" : "악재");
    const copy = document.createElement("span"); copy.className = "news-copy"; copy.textContent = item.headline;
    row.append(time,tag,copy); return row;
  });
  $("#newsList").replaceChildren(...newsRows);
  drawChart();
}

function setMetric(selector, text, value = 0) {
  const node = $(selector); node.textContent = text; node.classList.toggle("positive", value > 0); node.classList.toggle("negative", value < 0);
}

function drawChart() {
  const canvas = $("#priceChart"), rect = canvas.getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
  if (!rect.width || !rect.height) return;
  canvas.width = Math.round(rect.width * ratio); canvas.height = Math.round(rect.height * ratio);
  const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio);
  const width = rect.width, height = rect.height, pad = {left:8,right:8,top:10,bottom:8};
  ctx.clearRect(0,0,width,height);
  for (let n=1;n<=4;n++) { const y = pad.top + (height-pad.top-pad.bottom) * n / 5; ctx.strokeStyle="#26334a"; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(pad.left,y); ctx.lineTo(width-pad.right,y); ctx.stroke(); }
  const values = game.history[game.selected], low = Math.min(...values), high = Math.max(...values), margin = Math.max((high-low)*.12,1);
  const color = values.at(-1) >= values[0] ? "#3bd3a0" : "#ff7186";
  ctx.strokeStyle=color; ctx.lineWidth=2.5; ctx.lineJoin="round"; ctx.beginPath();
  values.forEach((value,j) => {
    const x=pad.left+j*(width-pad.left-pad.right)/Math.max(1,values.length-1);
    const y=height-pad.bottom-(value-(low-margin))/(high-low+2*margin)*(height-pad.top-pad.bottom);
    j===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
  }); ctx.stroke();
  const lastX=width-pad.right, lastY=height-pad.bottom-(values.at(-1)-(low-margin))/(high-low+2*margin)*(height-pad.top-pad.bottom);
  ctx.fillStyle=color;ctx.beginPath();ctx.arc(lastX,lastY,4,0,Math.PI*2);ctx.fill();
}

async function signIn() {
  if (!configReady) { $("#authError").textContent = "firebase_config.js에 Firebase 프로젝트 설정을 먼저 입력해 주세요."; return; }
  $("#authError").textContent = "";
  try { await signInWithPopup(auth, new GoogleAuthProvider()); }
  catch (error) { $("#authError").textContent = authErrorMessage(error); }
}

function authErrorMessage(error) {
  if (error.code === "auth/popup-closed-by-user") return "로그인 창이 닫혔습니다. 다시 시도해 주세요.";
  if (error.code === "auth/unauthorized-domain") return "현재 웹 주소를 Firebase Authentication의 승인된 도메인에 추가해 주세요.";
  return error.message || "Google 로그인에 실패했습니다.";
}

onAuthStateChanged(auth, async (user) => {
  game.currentUser = user;
  $("#signInButton").classList.toggle("hidden", Boolean(user));
  $("#heroSignInButton").classList.toggle("hidden", Boolean(user));
  $("#signOutButton").classList.toggle("hidden", !user);
  $("#rankingTab").classList.toggle("hidden", !user);
  $("#profileTab").classList.toggle("hidden", !user);
  $("#userBadge").classList.toggle("hidden", !user);
  if (!user) { game.title = ""; game.isCurrentLeader = false; $("#userBadge").textContent = ""; showView("authView"); return; }
  $("#userBadge").textContent = user.displayName || user.email;
  try {
    const profile = await getDoc(doc(db, "players", user.uid));
    const profileData = profile.exists() ? profile.data() : {};
    const nickname = profileData.nickname || "";
    game.title = isDeveloperAccount() && profileData.title === "개발자" ? "개발자" : "";
    if (nickname) { game.nickname = nickname; $("#userBadge").textContent = nickname; showView("gameView"); render(); }
    else { $("#nicknameError").textContent = ""; $("#nicknameInput").value = ""; $("#nicknameDialog").showModal(); }
  } catch (error) {
    showView("authView"); $("#authError").textContent = `계정 정보를 읽지 못했습니다. Firestore 규칙을 확인해 주세요. ${error.message}`;
  }
});

async function submitNickname(event) {
  event.preventDefault();
  const nickname = $("#nicknameInput").value.trim();
  if ([...nickname].length < 2 || [...nickname].length > 12) { $("#nicknameError").textContent = "닉네임은 2~12자로 입력해 주세요."; return; }
  const button = $("#nicknameForm button"); button.disabled = true;
  try {
    await setDoc(doc(db,"players",game.currentUser.uid), {nickname, email:game.currentUser.email || "", title:game.title});
    game.nickname = nickname; $("#userBadge").textContent = nickname; $("#nicknameDialog").close(); showView("gameView"); render();
  } catch (error) { $("#nicknameError").textContent = error.message; }
  finally { button.disabled = false; }
}

async function openProfile() {
  showView("profileView");
  if (profileLeaderUnsubscribe) profileLeaderUnsubscribe();
  profileLeaderUnsubscribe = null;
  game.isCurrentLeader = false;
  $("#profileStatus").textContent = "";
  $("#profileError").textContent = "";
  $("#profileEmail").textContent = game.currentUser?.email || "Google 계정";
  $("#profileNicknameInput").value = game.nickname;
  renderProfileTitles();
  const leaderQuery = query(collection(db,"rankings"),orderBy("score","desc"),limit(1));
  profileLeaderUnsubscribe = onSnapshot(leaderQuery, (snapshot) => {
    game.isCurrentLeader = !snapshot.empty && snapshot.docs[0].id === game.currentUser?.uid;
    renderProfileTitles();
  }, (error) => { $("#profileError").textContent = `칭호 정보를 불러오지 못했습니다. ${error.message}`; });
}

async function saveProfile(event) {
  event.preventDefault();
  const nickname = $("#profileNicknameInput").value.trim();
  if ([...nickname].length < 2 || [...nickname].length > 12) {
    $("#profileError").textContent = "닉네임은 2~12자로 입력해 주세요.";
    return;
  }
  const title = isDeveloperAccount() && $("#profileTitleSelect").value === "개발자" ? "개발자" : "";
  const button = $("#saveProfileButton");
  button.disabled = true;
  $("#profileStatus").textContent = "저장 중…";
  $("#profileError").textContent = "";
  try {
    const profileRef = doc(db,"players",game.currentUser.uid);
    const rankingRef = doc(db,"rankings",game.currentUser.uid);
    const ranking = await getDoc(rankingRef);
    const batch = writeBatch(db);
    batch.set(profileRef,{nickname,email:game.currentUser.email || "",title},{merge:true});
    if (ranking.exists()) batch.update(rankingRef,{nickname,title});
    await batch.commit();
    game.nickname = nickname;
    game.title = title;
    $("#userBadge").textContent = nickname;
    $("#profileStatus").textContent = "개인정보를 저장했습니다.";
    renderProfileTitles();
  } catch (error) {
    $("#profileStatus").textContent = "";
    $("#profileError").textContent = `저장하지 못했습니다. ${error.message}`;
  } finally { button.disabled = false; }
}

async function openRanking() {
  showView("rankingView"); $("#rankingRows").replaceChildren(); $("#rankingStatus").textContent = "랭킹을 불러오는 중…";
  if (rankingUnsubscribe) rankingUnsubscribe();
  const rankingQuery = query(collection(db,"rankings"),orderBy("score","desc"),limit(20));
  rankingUnsubscribe = onSnapshot(rankingQuery, (snapshot) => {
    $("#rankingRows").replaceChildren();
    if (snapshot.empty) { $("#rankingStatus").textContent = "아직 등록된 기록이 없습니다."; return; }
    $("#rankingStatus").textContent = "점수는 보유 현금 기준입니다. 기록 시각은 한국 표준시로 표시합니다.";
    snapshot.docs.forEach((item,index) => {
      const data=item.data(), row=document.createElement("tr");
      if (item.id === game.currentUser.uid) row.classList.add("own-row");
      const rank=document.createElement("td");rank.textContent=`${index+1}위`;
      const nickname=document.createElement("td"), name=document.createElement("span"), badges=document.createElement("span");
      name.textContent=data.nickname || "익명"; badges.className="title-badges ranking-title-badges";
      if (data.title === "개발자") addTitleBadge(badges,"개발자");
      if (index === 0) addTitleBadge(badges,"익절왕");
      nickname.append(name,badges);
      const score=document.createElement("td");score.textContent=won(data.score || 0);
      const stamp=document.createElement("td");stamp.textContent=data.updatedAt?.toDate ? formatLocalDate(data.updatedAt.toDate()) : "-";
      row.append(rank,nickname,score,stamp); $("#rankingRows").append(row);
    });
  }, (error) => { $("#rankingStatus").textContent = `랭킹을 불러오지 못했습니다. Firestore 규칙과 설정을 확인해 주세요. ${error.message}`; });
}

async function saveRanking() {
  const button = $("#confirmSaveButton"); button.disabled = true; $("#saveError").textContent = "";
  try {
    await setDoc(doc(db,"rankings",game.currentUser.uid), {
      nickname:game.nickname, score:Math.trunc(game.bestScore), updatedAt:serverTimestamp(), title:game.title
    });
    $("#confirmDialog").close(); resetGame(); showView("gameView");
  } catch (error) { $("#saveError").textContent = `저장하지 못했습니다. ${error.message}`; }
  finally { button.disabled = false; }
}

$("#signInButton").addEventListener("click", signIn);
$("#heroSignInButton").addEventListener("click", signIn);
$("#signOutButton").addEventListener("click", () => signOut(auth));
$("#nicknameForm").addEventListener("submit", submitNickname);
$("#rankingTab").addEventListener("click", openRanking);
$("#backToGameButton").addEventListener("click", () => showView("gameView"));
$("#profileTab").addEventListener("click", openProfile);
$("#profileBackButton").addEventListener("click", () => showView("gameView"));
$("#profileForm").addEventListener("submit", saveProfile);
$("#buyButton").addEventListener("click", () => trade(true));
$("#sellButton").addEventListener("click", () => trade(false));
$("#minusButton").addEventListener("click", () => { $("#quantityInput").value = Math.max(1,(Number($("#quantityInput").value)||1)-1); });
$("#plusButton").addEventListener("click", () => { $("#quantityInput").value = Math.min(9999,(Number($("#quantityInput").value)||1)+1); });
$("#enrollButton").addEventListener("click", () => { $("#confirmScore").textContent = won(game.bestScore); $("#saveError").textContent = ""; $("#confirmDialog").showModal(); });
$("#cancelSaveButton").addEventListener("click", () => $("#confirmDialog").close());
$("#confirmSaveButton").addEventListener("click", saveRanking);
window.addEventListener("resize", drawChart);

if (!configReady) {
  $("#authError").textContent = "firebase_config.js에 Firebase 프로젝트 값을 입력하면 로그인을 사용할 수 있습니다.";
}
addNews(0,true,"갤럭시 신제품 공개 기대감에 관심 집중");
addNews(5,true,"AI 메모리 수요 확대 전망");
addNews(2,false,"전기차 가격 경쟁 심화 우려");
render();
