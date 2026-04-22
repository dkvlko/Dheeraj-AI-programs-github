const socket = io();

socket.emit("ping", {msg: "hello"});
