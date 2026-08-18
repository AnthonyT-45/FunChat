var ws;

function renderChat(data) {
  var message = document.createElement("p");

  (data.badges || []).forEach(function (badge) {
    var img = document.createElement("img");
    img.src = badge.url;
    img.alt = badge.title;
    img.title = badge.title;
    img.className = "badge";
    message.appendChild(img);
  });

  var name = document.createElement("span");
  name.textContent = data.user + ": ";
  name.style.color = data.user_color || "inherit";
  name.style.fontWeight = "bolder";
  message.appendChild(name);

  var text = document.createElement("span");
  text.className = "text";
  if (data.effect) {
    text.classList.add("effect-" + data.effect);
  }
  text.textContent =
    data.effect === "scramble"
      ? scramble(data.chat_message)
      : data.chat_message;
  message.appendChild(text);

  document.getElementById("messages").appendChild(message);
  setTimeout(function () {
    message.classList.add("fading");
    message.addEventListener("transitionend", function () {
      message.remove();
    });
  }, 30000);
}

function connect() {
  var scheme = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(scheme + "//" + location.host + "/ws");

  ws.onmessage = function (event) {
    renderChat(JSON.parse(event.data));
  };

  // keep retrying so the overlay reconnects itself after a server restart
  ws.onclose = function () {
    setTimeout(connect, 1000);
  };
}

connect();
