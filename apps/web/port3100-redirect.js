const http = require("http");

const server = http.createServer((req, res) => {
  res.writeHead(302, { Location: `http://localhost:3000${req.url}` });
  res.end();
});

server.listen(3100, () => {
  console.log("Port 3100 redirector active -> http://localhost:3000");
});
