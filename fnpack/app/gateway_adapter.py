#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import re
import signal
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GatewayAdapter")

# 前端注入脚本：拦截 fetch 和 XMLHttpRequest，将 Authorization 改写为 X-V2rayA-Authorization
HOOK_SCRIPT = b"""<script>
(function(){
  var OF = window.fetch;
  if (OF) {
    window.fetch = function(input, init) {
      init = init || {};
      if (init.headers) {
        if (init.headers instanceof Headers) {
          if (init.headers.has('Authorization')) {
            init.headers.set('X-V2rayA-Authorization', init.headers.get('Authorization'));
            init.headers.delete('Authorization');
          }
        } else if (Array.isArray(init.headers)) {
          for (var i = 0; i < init.headers.length; i++) {
            if (init.headers[i][0].toLowerCase() === 'authorization') {
              init.headers[i][0] = 'X-V2rayA-Authorization';
            }
          }
        } else if (typeof init.headers === 'object') {
          for (var k in init.headers) {
            if (k.toLowerCase() === 'authorization') {
              init.headers['X-V2rayA-Authorization'] = init.headers[k];
              delete init.headers[k];
            }
          }
        }
      }
      return OF.apply(this, arguments);
    };
  }
  var OSRH = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.setRequestHeader = function(header, value) {
    if (header && header.toLowerCase() === 'authorization') {
      header = 'X-V2rayA-Authorization';
    }
    return OSRH.call(this, header, value);
  };
})();
</script>"""

async def read_headers(reader):
    """读取 HTTP 报文头部直到 \\r\\n\\r\\n"""
    buf = bytearray()
    while b"\r\n\r\n" not in buf:
        chunk = await reader.read(4096)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > 65536:
            break
    if b"\r\n\r\n" not in buf:
        return None, buf
    idx = buf.find(b"\r\n\r\n")
    return bytes(buf[:idx + 4]), bytes(buf[idx + 4:])

async def pipe(reader, writer):
    """双向流式透传（用于 WebSocket 或全双工通道）"""
    try:
        while not reader.at_eof():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

def rewrite_request_headers(header_bytes):
    """请求头转换：X-V2rayA-Authorization -> Authorization，并禁用内部 gzip 以便注入 HTML"""
    lines = header_bytes.split(b"\r\n")
    new_lines = []
    auth_val = None
    for line in lines:
        if not line:
            continue
        lower_line = line.lower()
        if lower_line.startswith(b"x-v2raya-authorization:"):
            auth_val = line.split(b":", 1)[1].strip()
        elif lower_line.startswith(b"authorization:"):
            # 丢弃网关可能残留的原 Authorization
            continue
        elif lower_line.startswith(b"accept-encoding:"):
            # 内部后端强制使用明文，便于注入 Hook 脚本
            new_lines.append(b"Accept-Encoding: identity")
        else:
            new_lines.append(line)
    
    if auth_val:
        new_lines.append(b"Authorization: " + auth_val)
    return b"\r\n".join(new_lines) + b"\r\n\r\n"

async def handle_client(client_reader, client_writer, target_sock):
    """处理来自网关的连接"""
    try:
        target_reader, target_writer = await asyncio.open_unix_connection(target_sock)
    except Exception as e:
        logger.error(f"连接后端 Socket 失败 ({target_sock}): {e}")
        client_writer.close()
        return

    try:
        while True:
            # 读取网关请求头
            req_headers, req_rest = await read_headers(client_reader)
            if not req_headers:
                break

            # 转换请求头并发送给后端
            new_req_headers = rewrite_request_headers(req_headers)
            target_writer.write(new_req_headers)
            if req_rest:
                target_writer.write(req_rest)
            await target_writer.drain()

            # WebSocket 升级请求透传
            is_ws = b"upgrade: websocket" in req_headers.lower()

            # 读取后端响应头
            resp_headers, resp_rest = await read_headers(target_reader)
            if not resp_headers:
                break

            if is_ws and b"101 Switching Protocols" in resp_headers:
                client_writer.write(resp_headers)
                if resp_rest:
                    client_writer.write(resp_rest)
                await client_writer.drain()
                await asyncio.gather(
                    pipe(client_reader, target_writer),
                    pipe(target_reader, client_writer)
                )
                return

            # HTML 页面注入 Hook 脚本
            headers_lower = resp_headers.lower()
            is_html = b"content-type:" in headers_lower and b"text/html" in headers_lower
            cl_match = re.search(rb"content-length:\s*(\d+)", headers_lower)
            content_length = int(cl_match.group(1)) if cl_match else None
            is_chunked = bool(re.search(rb"transfer-encoding:\s*chunked", headers_lower))

            if is_html and content_length is not None:
                body = bytearray(resp_rest)
                while len(body) < content_length:
                    chunk = await target_reader.read(content_length - len(body))
                    if not chunk:
                        break
                    body.extend(chunk)

                head_idx = body.lower().find(b"<head>")
                if head_idx != -1:
                    new_body = bytes(body[:head_idx + 6]) + HOOK_SCRIPT + bytes(body[head_idx + 6:])
                else:
                    new_body = HOOK_SCRIPT + bytes(body)

                new_resp_headers = re.sub(
                    rb"(?i)content-length:\s*\d+",
                    b"Content-Length: " + str(len(new_body)).encode("ascii"),
                    resp_headers
                )
                client_writer.write(new_resp_headers)
                client_writer.write(new_body)
                await client_writer.drain()
            else:
                client_writer.write(resp_headers)
                if resp_rest:
                    client_writer.write(resp_rest)
                await client_writer.drain()

                if content_length is not None:
                    remaining = content_length - len(resp_rest)
                    while remaining > 0:
                        chunk = await target_reader.read(min(remaining, 65536))
                        if not chunk:
                            break
                        client_writer.write(chunk)
                        await client_writer.drain()
                        remaining -= len(chunk)
                elif is_chunked:
                    while True:
                        chunk = await target_reader.read(4096)
                        if not chunk:
                            break
                        client_writer.write(chunk)
                        await client_writer.drain()
                        if chunk.endswith(b"0\r\n\r\n") or b"\r\n0\r\n\r\n" in chunk:
                            break

            if b"connection: close" in req_headers.lower() or b"connection: close" in headers_lower:
                break
    except Exception as e:
        logger.debug(f"连接处理异常: {e}")
    finally:
        try:
            client_writer.close()
            target_writer.close()
        except Exception:
            pass

async def main():
    parser = argparse.ArgumentParser(description="fnOS Gateway Adapter for v2rayA")
    parser.add_argument("--listen", required=True, help="飞牛网关连接的 Socket 路径")
    parser.add_argument("--target", required=True, help="真实 v2rayA 监听的 Socket 路径")
    args = parser.parse_args()

    if os.path.exists(args.listen):
        os.remove(args.listen)

    server = await asyncio.start_unix_server(
        lambda r, w: handle_client(r, w, args.target),
        path=args.listen
    )
    os.chmod(args.listen, 0o666)
    logger.info(f"Adapter 已就绪: {args.listen} -> {args.target}")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    logger.info("正在退出 Adapter...")
    server.close()
    await server.wait_closed()
    if os.path.exists(args.listen):
        os.remove(args.listen)

if __name__ == "__main__":
    asyncio.run(main())
