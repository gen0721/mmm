const tg = window.Telegram.WebApp;
tg.expand();

// Функция пополнения через Crypto Bot
async function deposit() {
    tg.HapticFeedback.impactOccurred('heavy');
    const amount = await new Promise(resolve => {
        const val = prompt("Введите сумму пополнения (€):", "10");
        resolve(val);
    });

    if (!amount || isNaN(amount)) return;

    // Запрос к твоему серверу (server.js)
    try {
        const res = await fetch('/api/create-order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                userId: tg.initDataUnsafe.user?.id, 
                price: amount 
            })
        });
        const data = await res.json();
        
        if (data.url) {
            tg.openLink(data.url); // Открываем счет в Crypto Bot
        }
    } catch (e) {
        tg.showAlert("Ошибка платежной системы!");
    }
}

// Проверка на админа (anva4ik)
function checkAdmin() {
    const adminId = 12345678; // ЗАМЕНИ НА СВОЙ ID
    if (tg.initDataUnsafe.user?.id === adminId) {
        document.getElementById('admin-panel').style.display = 'block';
    }
}

// Анимация появления при скролле
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = 1;
            entry.target.style.transform = "translateY(0)";
        }
    });
});

document.querySelectorAll('.imba-card').forEach(card => observer.observe(card));
checkAdmin();
