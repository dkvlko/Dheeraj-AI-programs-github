const socket = io("http://192.168.29.25:8000");

const bottom = document.getElementById("bottom");

let lastX = null;
let lastY = null;

bottom.addEventListener("touchstart", (e) => {
    const t = e.touches[0];
    lastX = t.clientX;
    lastY = t.clientY;
});

bottom.addEventListener("touchmove", (e) => {
    e.preventDefault();

    const t = e.touches[0];
    let dx = t.clientX - lastX;
    let dy = t.clientY - lastY;

    lastX = t.clientX;
    lastY = t.clientY;

    socket.emit("touchpad_move", { dx: dx, dy: dy });
});

bottom.addEventListener("touchend", () => {
    lastX = null;
    lastY = null;
});

// Mouse support (desktop testing)
bottom.addEventListener("mousedown", (e) => {
    lastX = e.clientX;
    lastY = e.clientY;
});

bottom.addEventListener("mousemove", (e) => {
    if (lastX === null) return;

    let dx = e.clientX - lastX;
    let dy = e.clientY - lastY;

    lastX = e.clientX;
    lastY = e.clientY;

    socket.emit("touchpad_move", { dx: dx, dy: dy });
});

bottom.addEventListener("mouseup", () => {
    lastX = null;
    lastY = null;
});

// Optional: tap = click
bottom.addEventListener("click", () => {
    socket.emit("click");
});
