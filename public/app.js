const tg = window.Telegram.WebApp;
tg.expand();

// Данные для слайдера и каталога
const trends = [
    { title: "Dota 2: Arcana Bundle", price: "29.99€", img: "⚔️" },
    { title: "CS2: Karambit Doppler", price: "850€", img: "🔪" },
    { title: "GTA V: Money Boost", price: "15€", img: "💰" }
];

const items = [
    { name: "Global Elite Acc", game: "CS2", price: 45, type: "acc" },
    { name: "Immortal Rank", game: "Dota 2", price: 120, type: "service" },
    { name: "Prime Status", game: "CS2", price: 15, type: "item" },
    { name: "Shark Card", game: "GTA 5", price: 20, type: "service" }
];

function init() {
    // Движение свечения за пальцем
    window.addEventListener('mousemove', (e) => {
        gsap.to("#cursor-glow", { x: e.clientX, y: e.clientY, duration: 0.5 });
    });

    renderHero();
    renderCatalog(items);

    // Анимация появления элементов
    gsap.from(".hero-card", { opacity: 0, x: 50, stagger: 0.2, duration: 1 });
}

function renderHero() {
    const track = document.getElementById('hero-track');
    track.innerHTML = trends.map(t => `
        <div class="hero-card">
            <div style="font-size: 40px; z-index: 1">${t.img}</div>
            <div style="z-index: 1">
                <h4 style="margin: 0">${t.title}</h4>
                <div style="color: #00ffcc; font-weight: 800">${t.price}</div>
            </div>
        </div>
    `).join('');
}

function renderCatalog(data) {
    const grid = document.getElementById('main-catalog');
    grid.innerHTML = data.map(i => `
        <div class="p-card">
            <div style="font-size: 12px; opacity: 0.5">${i.game}</div>
            <div style="font-weight: 700; margin: 5px 0">${i.name}</div>
            <div style="color: #00ffcc">${i.price} €</div>
            <button class="buy-small" onclick="handleOrder(${i.price})">+</button>
        </div>
    `).join('');
}

function toggleCatalog() {
    const overlay = document.getElementById('catalog-overlay');
    const isVisible = overlay.style.display === 'block';
    
    if (isVisible) {
        gsap.to(".overlay", { opacity: 0, duration: 0.3, onComplete: () => overlay.style.display = 'none' });
    } else {
        overlay.style.display = 'block';
        gsap.fromTo(".overlay", { opacity: 0 }, { opacity: 1, duration: 0.3 });
        gsap.from(".cat-item", { x: -30, opacity: 0, stagger: 0.1 });
    }
}

async function handleOrder(price) {
    tg.HapticFeedback.impactOccurred('heavy');
    // Интеграция с твоим сервером
    alert("Создание заказа на " + price + "€");
}

init();
