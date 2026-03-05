const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

const data = {
    user: tg.initDataUnsafe.user || { first_name: "anva4ik" },
    items: [
        { id: 1, title: "Knife Fade", price: 450, tag: "CS2", color: "#ff4b2b" },
        { id: 2, title: "Dragonclaw Hook", price: 180, tag: "DOTA 2", color: "#4facfe" },
        { id: 3, title: "100M GTA Cash", price: 15, tag: "GTA 5", color: "#00f2fe" },
        { id: 4, title: "Account 7000 MMR", price: 110, tag: "DOTA 2", color: "#bc13fe" }
    ]
};

function setup() {
    document.getElementById('user-name').innerText = data.user.first_name;
    document.getElementById('user-avatar').innerText = data.user.first_name[0];

    renderCatalog();
    renderOffers();

    // GSAP Анимация появления
    gsap.from(".item-card", { opacity: 0, scale: 0.8, stagger: 0.1, duration: 0.6, ease: "back.out(1.7)" });
}

function renderOffers() {
    const slider = document.getElementById('featured-slider');
    const offers = [
        { t: "Скидка -20% на все скины", c: "linear-gradient(45deg, #f093fb, #f5576c)" },
        { t: "Новое поступление CS2", c: "linear-gradient(45deg, #5ee7df, #b490ca)" }
    ];
    slider.innerHTML = offers.map(o => `
        <div class="offer-card" style="background: ${o.c}; opacity: 0.9">
            <h2 style="margin:0">${o.t}</h2>
            <button style="margin-top:20px; border:none; padding:10px 20px; border-radius:10px; font-weight:bold">Смотреть</button>
        </div>
    `).join('');
}

function renderCatalog() {
    const grid = document.getElementById('market-grid');
    grid.innerHTML = data.items.map(i => `
        <div class="item-card" onclick="buy(${i.id}, ${i.price})">
            <div style="font-size: 10px; color: ${i.color}; font-weight: 800; text-transform: uppercase">${i.tag}</div>
            <div style="font-size: 16px; font-weight: bold; margin: 10px 0">${i.title}</div>
            <div style="font-size: 18px; font-weight: 900; color: #fff">${i.price} €</div>
        </div>
    `).join('');
}

function nav(el) {
    document.querySelectorAll('.tab-item').forEach(i => i.classList.remove('active'));
    el.classList.add('active');
    tg.HapticFeedback.selectionChanged();
}

async function buy(id, price) {
    tg.HapticFeedback.impactOccurred('heavy');
    tg.showConfirm(`Подтверждаете покупку за ${price}€?`, (ok) => {
        if(ok) tg.showAlert("Счет сформирован! Проверьте бота.");
    });
}

setup();
