import AppKit
import CoreGraphics
import Foundation

let output = URL(fileURLWithPath: "/Users/wuzehe/Documents/New project/ai-infra-impact-map-2026-05-09.pdf")
var mediaBox = CGRect(x: 0, y: 0, width: 842, height: 595)

guard let consumer = CGDataConsumer(url: output as CFURL),
      let context = CGContext(consumer: consumer, mediaBox: &mediaBox, nil) else {
  fatalError("Cannot create PDF context")
}

context.beginPDFPage(nil)
context.translateBy(x: 0, y: mediaBox.height)
context.scaleBy(x: 1, y: -1)
NSGraphicsContext.current = NSGraphicsContext(cgContext: context, flipped: true)

func color(_ hex: UInt32) -> NSColor {
  let r = CGFloat((hex >> 16) & 0xff) / 255
  let g = CGFloat((hex >> 8) & 0xff) / 255
  let b = CGFloat(hex & 0xff) / 255
  return NSColor(calibratedRed: r, green: g, blue: b, alpha: 1)
}

let ink = color(0x17212f)
let muted = color(0x5f6d7e)
let line = color(0xdbe3ec)
let paper = color(0xf3f6f8)
let panel = color(0xfbfcfe)
let green = color(0x15803d)
let cyan = color(0x0e7490)
let amber = color(0xa16207)
let red = color(0xb42318)
let dark = color(0x17212f)
let white = color(0xffffff)

func font(_ size: CGFloat, weight: NSFont.Weight = .regular) -> NSFont {
  NSFont.systemFont(ofSize: size, weight: weight)
}

func drawText(_ text: String, _ rect: CGRect, size: CGFloat, weight: NSFont.Weight = .regular, color textColor: NSColor = ink, align: NSTextAlignment = .left, lineHeight: CGFloat? = nil) {
  let paragraph = NSMutableParagraphStyle()
  paragraph.alignment = align
  paragraph.lineBreakMode = .byWordWrapping
  if let lineHeight {
    paragraph.minimumLineHeight = lineHeight
    paragraph.maximumLineHeight = lineHeight
  }
  let attrs: [NSAttributedString.Key: Any] = [
    .font: font(size, weight: weight),
    .foregroundColor: textColor,
    .paragraphStyle: paragraph
  ]
  NSString(string: text).draw(in: rect, withAttributes: attrs)
}

func fillRounded(_ rect: CGRect, _ fill: NSColor, stroke: NSColor? = nil, radius: CGFloat = 8, width: CGFloat = 1) {
  let path = NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius)
  fill.setFill()
  path.fill()
  if let stroke {
    stroke.setStroke()
    path.lineWidth = width
    path.stroke()
  }
}

func drawTag(_ text: String, x: CGFloat, y: CGFloat, w: CGFloat) {
  fillRounded(CGRect(x: x, y: y, width: w, height: 22), color(0xe7f7fb), stroke: color(0xb8e8f2), radius: 11)
  drawText(text, CGRect(x: x, y: y + 3, width: w, height: 16), size: 10, weight: .bold, color: cyan, align: .center)
}

func drawArrow(from: CGPoint, to: CGPoint, color arrowColor: NSColor = color(0x94a3b8)) {
  arrowColor.setStroke()
  let p = NSBezierPath()
  p.move(to: from)
  p.line(to: to)
  p.lineWidth = 1.6
  p.stroke()
  arrowColor.setFill()
  let head = NSBezierPath()
  head.move(to: to)
  head.line(to: CGPoint(x: to.x - 6, y: to.y - 4))
  head.line(to: CGPoint(x: to.x - 6, y: to.y + 4))
  head.close()
  head.fill()
}

func drawStep(_ title: String, _ body: String, rect: CGRect) {
  fillRounded(rect, white, stroke: line, radius: 8)
  drawText(title, CGRect(x: rect.minX + 7, y: rect.minY + 9, width: rect.width - 14, height: 18), size: 9.6, weight: .bold, align: .center)
  drawText(body, CGRect(x: rect.minX + 7, y: rect.minY + 31, width: rect.width - 14, height: rect.height - 38), size: 7.8, color: muted, align: .center, lineHeight: 10)
}

paper.setFill()
NSBezierPath(rect: mediaBox).fill()
fillRounded(CGRect(x: 18, y: 18, width: 806, height: 559), white, stroke: line, radius: 0)

drawText("英伟达“铜转光”与英特尔大涨：对电力 / AIDC / 算电协同看板的影响",
         CGRect(x: 40, y: 34, width: 505, height: 62), size: 21, weight: .bold, lineHeight: 25)
drawText("结论版本：真实、简洁、按传导强弱排序。日期：2026-05-09",
         CGRect(x: 40, y: 91, width: 460, height: 18), size: 10.5, color: muted)

fillRounded(CGRect(x: 570, y: 34, width: 225, height: 74), color(0xe8f7ef), stroke: color(0xb7e4c7), radius: 8)
drawText("核心判断", CGRect(x: 584, y: 46, width: 195, height: 19), size: 13, weight: .bold, color: green)
drawText("短线更利好算力硬件与 AIDC 承载，不是直接利好电力主线。电力链需要等第二层传导。",
         CGRect(x: 584, y: 67, width: 195, height: 34), size: 9.5, color: color(0x0f2c22), lineHeight: 13)

dark.setStroke()
let headerLine = NSBezierPath()
headerLine.move(to: CGPoint(x: 40, y: 122))
headerLine.line(to: CGPoint(x: 795, y: 122))
headerLine.lineWidth = 1.8
headerLine.stroke()

let leftCard = CGRect(x: 40, y: 138, width: 368, height: 128)
let rightCard = CGRect(x: 424, y: 138, width: 371, height: 128)
fillRounded(leftCard, panel, stroke: line, radius: 8)
fillRounded(rightCard, panel, stroke: line, radius: 8)

drawTag("消息 1", x: 54, y: 153, w: 48)
drawText("英伟达铜转光", CGRect(x: 112, y: 151, width: 230, height: 22), size: 15, weight: .bold)
let leftSteps = [
  ("GPU 集群", "训练与推理集群继续扩大"),
  ("铜缆瓶颈", "距离、功耗、信号衰减受限"),
  ("光互联", "光模块、交换机、PCB 先受益"),
  ("AIDC", "高密度机房、上架率"),
  ("电力配套", "储能、液冷、配电、绿电直供")
]
for i in 0..<5 {
  let x = 54 + CGFloat(i) * 68
  drawStep(leftSteps[i].0, leftSteps[i].1, rect: CGRect(x: x, y: 184, width: 58, height: 66))
  if i < 4 { drawArrow(from: CGPoint(x: x + 58, y: 217), to: CGPoint(x: x + 66, y: 217)) }
}

drawTag("消息 2", x: 438, y: 153, w: 48)
drawText("英特尔周五盘后大涨", CGRect(x: 496, y: 151, width: 230, height: 22), size: 15, weight: .bold)
let rightSteps = [
  ("Apple 代工", "市场交易客户突破"),
  ("政策重估", "美国本土制造支持升温"),
  ("代工情绪", "先进制造、封装、设备"),
  ("国产映射", "中芯情绪跟随"),
  ("AIDC 扩散", "算力基础设施风险偏好提升")
]
for i in 0..<5 {
  let x = 438 + CGFloat(i) * 68
  drawStep(rightSteps[i].0, rightSteps[i].1, rect: CGRect(x: x, y: 184, width: 58, height: 66))
  if i < 4 { drawArrow(from: CGPoint(x: x + 58, y: 217), to: CGPoint(x: x + 66, y: 217)) }
}

let rankRect = CGRect(x: 40, y: 283, width: 755, height: 153)
fillRounded(rankRect, dark, stroke: dark, radius: 8)
drawText("影响强弱排序", CGRect(x: 56, y: 298, width: 180, height: 22), size: 15, weight: .bold, color: white)

let bars: [(String, CGFloat, String)] = [
  ("光模块 / CPO / PCB / 交换机", 0.96, "第一受益层"),
  ("AIDC 承载", 0.78, "润泽 / 光环"),
  ("液冷 / 电源 / 储能", 0.62, "阳光电源"),
  ("国产芯片", 0.55, "中芯情绪修复"),
  ("电力资源 / 数字电网", 0.38, "第二层传导"),
  ("纯电力运营", 0.28, "需事件确认")
]

for (i, item) in bars.enumerated() {
  let y = 328 + CGFloat(i) * 17
  drawText(item.0, CGRect(x: 56, y: y - 2, width: 180, height: 14), size: 9.5, weight: .semibold, color: white)
  fillRounded(CGRect(x: 246, y: y, width: 390, height: 11), color(0x334155), radius: 6)
  fillRounded(CGRect(x: 246, y: y, width: 390 * item.1, height: 11), color(0x38bdf8), radius: 6)
  drawText(item.2, CGRect(x: 650, y: y - 2, width: 118, height: 14), size: 9.5, color: color(0xcbd5e1), align: .right)
}

let mY: CGFloat = 452
let cardW: CGFloat = 238
let matrixCards = [
  ("看板里优先盯", ["润泽科技 / 光环新网：AIDC 承载层资金是否回流。", "阳光电源：储能、电源、AIDC 产品订单是否落地。", "中芯国际：半导体情绪修复能否带动承接。"]),
  ("不要误判", ["铜转光不是直接利好协鑫能科、南网数字、大唐发电。", "英特尔大涨是晶圆代工重估，不是中国电力股订单确认。", "电力主线要等绿电直供、长协电价、AIDC 项目或资金连续性。"]),
  ("操作性结论", ["强：算力硬件、光互联、AIDC 承载。", "中：储能、电源、液冷、国产芯片情绪。", "弱：纯电力运营，除非出现项目与资金验证。"])
]

for (i, card) in matrixCards.enumerated() {
  let x = 40 + CGFloat(i) * (cardW + 20)
  fillRounded(CGRect(x: x, y: mY, width: cardW, height: 85), panel, stroke: line, radius: 8)
  drawText(card.0, CGRect(x: x + 12, y: mY + 11, width: cardW - 24, height: 18), size: 12.5, weight: .bold)
  for (j, lineText) in card.1.enumerated() {
    let bulletColor = i == 2 && j == 0 ? green : (i == 2 && j == 1 ? amber : (i == 2 && j == 2 ? red : muted))
    drawText("•", CGRect(x: x + 13, y: mY + 34 + CGFloat(j) * 14, width: 10, height: 12), size: 9.5, color: bulletColor)
    drawText(lineText, CGRect(x: x + 25, y: mY + 32 + CGFloat(j) * 14, width: cardW - 36, height: 18), size: 8.8, color: color(0x405064), lineHeight: 11)
  }
}

line.setStroke()
let footerLine = NSBezierPath()
footerLine.move(to: CGPoint(x: 40, y: 552))
footerLine.line(to: CGPoint(x: 795, y: 552))
footerLine.lineWidth = 1
footerLine.stroke()
drawText("一句话：先看算力硬件和 AIDC，电力链等第二层传导确认。",
         CGRect(x: 40, y: 560, width: 350, height: 14), size: 8.5, color: muted)
drawText("参考：NVIDIA 互联趋势、Intel/Apple 代工消息、东方财富/腾讯行情看板数据。",
         CGRect(x: 470, y: 560, width: 325, height: 14), size: 8.5, color: muted, align: .right)

context.endPDFPage()
context.closePDF()
