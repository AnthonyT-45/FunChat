var ws;

function connect() {
  var scheme = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(scheme + "//" + location.host + "/ws");

  ws.onmessage = function (event) {
    var data = JSON.parse(event.data);
    var chatbox = document.querySelector(".chatbox");
    var messages = document.getElementById("messages");
    var message = document.createElement("p");
    var name = document.createElement("span");
    name.textContent = data.user + ": ";
    name.style.color = data.user_color || "inherit";
    name.style.fontWeight = "bolder";
    message.appendChild(name);
    message.appendChild(document.createTextNode(data.chat_message));
    messages.appendChild(message);
    chatbox.appendChild(messages);
    setTimeout(function () {
      message.classList.add("fading");
      message.addEventListener("transitionend", function () {
        message.remove();
      });
    }, 30000);
  };

  // overlay should have original contents if the server restarts or the socket disconnects
  ws.onclose = function () {
    setTimeout(connect, 1000);
  };
}

connect();

function events() {}
