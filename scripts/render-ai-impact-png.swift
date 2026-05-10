import AppKit
import Foundation

let width = 1400
let height = 1180
let output = URL(fileURLWithPath: "/Users/wuzehe/Documents/New project/ai-infra-impact-map-2026-05-09.png")

guard let rep = NSBitmapImageRep(
  bitmapDataPlanes: nil,
  pixelsWide: width,
  pixelsHigh: height,
  bitsPerSample: 8,
  samplesPerPixel: 4,
  hasAlpha: true,
  isPlanar: false,
  colorSpaceName: .deviceRGB,
  bytesPerRow: 0,
  bitsPerPixel: 0
) else {
  fatalError("Cannot create bitmap")
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

func c(_ hex: UInt32, _ alpha: CGFloat = 1) -> NSColor {
  NSColor(calibratedRed: CGFloat((hex >> 16) & 0xff) / 255,
          green: CGFloat((hex >> 8) & 0xff) / 255,
          blue: CGFloat(hex & 0xff) / 255,
          alpha: alpha)
}

let ink = c(0x17212f)
let muted = c(0x5f6d7e)
let line = c(0xd9e2ec)
let paper = c(0xedf2f6)
let dark = c(0x182433)
let white = c(0xffffff)
let cyan = c(0x0e7490)
let green = c(0x15803d)
let amber = c(0xa16207)
let red = c(0xb42318)

func font(_ size: CGFloat, _ weight: NSFont.Weight = .regular) -> NSFont {
  NSFont.systemFont(ofSize: size, weight: weight)
}

func text(_ s: String, _ r: CGRect, _ size: CGFloat, _ weight: NSFont.Weight = .regular, _ color: NSColor = ink, _ align: NSTextAlignment = .left) {
  let rr = CGRect(x: r.minX, y: CGFloat(height) - r.minY - r.height, width: r.width, height: r.height)
  let p = NSMutableParagraphStyle()
  p.alignment = align
  p.lineBreakMode = .byWordWrapping
  let attrs: [NSAttributedString.Key: Any] = [
    .font: font(size, weight),
    .foregroundColor: color,
    .paragraphStyle: p
  ]
  NSString(string: s).draw(in: rr, withAttributes: attrs)
}

func round(_ r: CGRect, fill: NSColor, stroke: NSColor? = nil, radius: CGFloat = 20, lineWidth: CGFloat = 1.5) {
  let rr = CGRect(x: r.minX, y: CGFloat(height) - r.minY - r.height, width: r.width, height: r.height)
  let p = NSBezierPath(roundedRect: rr, xRadius: radius, yRadius: radius)
  fill.setFill()
  p.fill()
  if let stroke {
    stroke.setStroke()
    p.lineWidth = lineWidth
    p.stroke()
  }
}

func rect(_ r: CGRect, _ fill: NSColor) {
  let rr = CGRect(x: r.minX, y: CGFloat(height) - r.minY - r.height, width: r.width, height: r.height)
  fill.setFill()
  NSBezierPath(rect: rr).fill()
}

func linePath(_ points: [CGPoint], _ color: NSColor, _ width: CGFloat = 2) {
  guard let first = points.first else { return }
  let convertedFirst = CGPoint(x: first.x, y: CGFloat(height) - first.y)
  let p = NSBezierPath()
  p.move(to: convertedFirst)
  for pt in points.dropFirst() {
    p.line(to: CGPoint(x: pt.x, y: CGFloat(height) - pt.y))
  }
  color.setStroke()
  p.lineWidth = width
  p.stroke()
}

func step(_ x: CGFloat, _ y: CGFloat, _ title: String, _ body: String) {
  round(CGRect(x: x, y: y, width: 118, height: 100), fill: white, stroke: line, radius: 16)
  text(title, CGRect(x: x + 14, y: y + 20, width: 90, height: 28), 21, .bold)
  text(body, CGRect(x: x + 14, y: y + 58, width: 90, height: 28), 17, .regular, muted)
}

paper.setFill()
NSBezierPath(rect: CGRect(x: 0, y: 0, width: width, height: height)).fill()
round(CGRect(x: 70, y: 54, width: 1260, height: 1072), fill: white, stroke: line, radius: 28)

round(CGRect(x: 70, y: 54, width: 1260, height: 284), fill: dark, radius: 28)
rect(CGRect(x: 70, y: 260, width: 1260, height: 78), dark)
text("AI INFRA TRANSMISSION MAP", CGRect(x: 118, y: 92, width: 500, height: 28), 18, .bold, c(0x9bd8ee))
text("两条海外消息，怎么传导到", CGRect(x: 118, y: 142, width: 760, height: 70), 58, .heavy, white)
text("电力 / AIDC / 算电协同？", CGRect(x: 118, y: 210, width: 760, height: 70), 58, .heavy, white)
text("先抬升算力硬件与 AIDC 承载，再向储能、电源、液冷和绿电直供扩散。", CGRect(x: 118, y: 284, width: 820, height: 34), 24, .regular, c(0xc8d5e2))

round(CGRect(x: 1018, y: 104, width: 250, height: 168), fill: c(0xffffff, 0.09), stroke: c(0xffffff, 0.24), radius: 22)
round(CGRect(x: 1042, y: 128, width: 92, height: 34), fill: c(0xa7f3d0), radius: 17)
text("结论", CGRect(x: 1064, y: 134, width: 50, height: 24), 18, .bold)
text("先看算力硬件", CGRect(x: 1042, y: 178, width: 190, height: 34), 24, .bold, white)
text("和 AIDC", CGRect(x: 1042, y: 214, width: 160, height: 34), 24, .bold, white)

round(CGRect(x: 118, y: 386, width: 566, height: 230), fill: c(0xfbfdff), stroke: line, radius: 24)
round(CGRect(x: 716, y: 386, width: 566, height: 230), fill: c(0xfbfdff), stroke: line, radius: 24)
round(CGRect(x: 146, y: 420, width: 92, height: 36), fill: c(0xe6f7fb), radius: 18)
text("消息 1", CGRect(x: 166, y: 426, width: 60, height: 24), 18, .bold, cyan)
text("英伟达：铜转光", CGRect(x: 260, y: 414, width: 320, height: 44), 34, .heavy)
round(CGRect(x: 744, y: 420, width: 92, height: 36), fill: c(0xe6f7fb), radius: 18)
text("消息 2", CGRect(x: 764, y: 426, width: 60, height: 24), 18, .bold, cyan)
text("英特尔：盘后大涨", CGRect(x: 858, y: 414, width: 350, height: 44), 34, .heavy)

let left = [(146.0, "GPU", "集群扩大"), (278.0, "铜缆", "功耗瓶颈"), (410.0, "光互联", "CPO/PCB"), (542.0, "AIDC", "机房承载")]
for item in left { step(item.0, 482, item.1, item.2) }
linePath([CGPoint(x: 266, y: 532), CGPoint(x: 276, y: 532), CGPoint(x: 398, y: 532), CGPoint(x: 408, y: 532), CGPoint(x: 530, y: 532), CGPoint(x: 540, y: 532)], c(0x94a3b8), 3)

let right = [(744.0, "Apple", "代工预期"), (876.0, "政策", "制造溢价"), (1008.0, "代工链", "先进制造"), (1140.0, "国产芯片", "情绪映射")]
for item in right { step(item.0, 482, item.1, item.2) }
linePath([CGPoint(x: 864, y: 532), CGPoint(x: 874, y: 532), CGPoint(x: 996, y: 532), CGPoint(x: 1006, y: 532), CGPoint(x: 1128, y: 532), CGPoint(x: 1138, y: 532)], c(0x94a3b8), 3)

round(CGRect(x: 118, y: 660, width: 1164, height: 282), fill: dark, radius: 26)
text("影响强弱排序", CGRect(x: 154, y: 694, width: 260, height: 44), 34, .heavy, white)
let bars: [(String, CGFloat, String)] = [
  ("光模块 / CPO / PCB / 交换机", 0.96, "第一受益层"),
  ("AIDC 承载", 0.78, "润泽 / 光环"),
  ("液冷 / 电源 / 储能", 0.62, "阳光电源"),
  ("国产芯片", 0.55, "中芯情绪"),
  ("电力资源 / 数字电网", 0.38, "第二层传导")
]
for (i, b) in bars.enumerated() {
  let y = CGFloat(750 + i * 38)
  text(b.0, CGRect(x: 154, y: y - 23, width: 330, height: 30), 24, .bold, white)
  round(CGRect(x: 514, y: y - 18, width: 560, height: 20), fill: c(0x334155), radius: 10)
  round(CGRect(x: 514, y: y - 18, width: 560 * b.1, height: 20), fill: c(0x38bdf8), radius: 10)
  text(b.2, CGRect(x: 1104, y: y - 22, width: 130, height: 26), 18, .regular, c(0xcbd5e1), .right)
}

func stockCard(_ x: CGFloat, _ title: String, _ sub: String, _ color: NSColor) {
  round(CGRect(x: x, y: 974, width: 360, height: 76), fill: white, stroke: line, radius: 20)
  text(title, CGRect(x: x + 28, y: 992, width: 310, height: 28), 24, .bold, color)
  text(sub, CGRect(x: x + 28, y: 1024, width: 310, height: 22), 18, .regular, muted)
}
stockCard(118, "优先盯：润泽 / 光环", "资金回流、上架率、客户包销。", green)
stockCard(520, "中等传导：阳光 / 中芯", "订单落地和半导体情绪持续性。", amber)
stockCard(922, "等待确认：协鑫 / 南网 / 大唐", "绿电直供、长协电价、资金验证。", red)

text("一句话：这两条消息短线更偏“算力硬件 / AIDC 承载”，电力资源股是后排传导，不能直接当强利好处理。", CGRect(x: 118, y: 1074, width: 1160, height: 32), 22, .regular, muted)

NSGraphicsContext.restoreGraphicsState()
guard let data = rep.representation(using: .png, properties: [:]) else {
  fatalError("Cannot encode PNG")
}
try data.write(to: output)
