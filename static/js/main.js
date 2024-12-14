document.addEventListener("DOMContentLoaded", () => {
    const userCards = document.querySelectorAll(".user-card");
    userCards.forEach(card => {
        card.addEventListener("click", () => {
            alert(`Has seleccionado al usuario: ${card.querySelector("h2").innerText}`);
        });
    });
});
