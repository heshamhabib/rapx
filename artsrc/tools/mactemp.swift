// Prints the Mac's temperatures and thermal state as JSON, without root (same HID sensors as Stats / iStat):
//   {"cpu": <hottest CPU die sensor, C>, "cpu_avg": <average>, "battery": <C or null>, "thermal": "nominal|fair|serious|critical"}
// Build: swiftc -O artsrc/tools/mactemp.swift -o artsrc/tools/mactemp
import Foundation
import IOKit

// Private IOHIDEventSystem API (stable for years; used by many monitoring tools)
@_silgen_name("IOHIDEventSystemClientCreate") func IOHIDEventSystemClientCreate(_ allocator: CFAllocator?) -> Unmanaged<AnyObject>
@_silgen_name("IOHIDEventSystemClientSetMatching") func IOHIDEventSystemClientSetMatching(_ client: AnyObject, _ matching: CFDictionary) -> Int32
@_silgen_name("IOHIDEventSystemClientCopyServices") func IOHIDEventSystemClientCopyServices(_ client: AnyObject) -> Unmanaged<CFArray>?
@_silgen_name("IOHIDServiceClientCopyProperty") func IOHIDServiceClientCopyProperty(_ service: AnyObject, _ key: CFString) -> Unmanaged<AnyObject>?
@_silgen_name("IOHIDServiceClientCopyEvent") func IOHIDServiceClientCopyEvent(_ service: AnyObject, _ type: Int64, _ options: Int32, _ timestamp: Int64) -> Unmanaged<AnyObject>?
@_silgen_name("IOHIDEventGetFloatValue") func IOHIDEventGetFloatValue(_ event: AnyObject, _ field: Int32) -> Double

let kTemperatureEvent: Int64 = 15
let kTemperatureField: Int32 = 15 << 16

func sensors() -> [(String, Double)] {
    let client = IOHIDEventSystemClientCreate(kCFAllocatorDefault).takeRetainedValue()
    let matching = ["PrimaryUsagePage": 0xff00, "PrimaryUsage": 5] as CFDictionary
    _ = IOHIDEventSystemClientSetMatching(client, matching)
    guard let services = IOHIDEventSystemClientCopyServices(client)?.takeRetainedValue() as? [AnyObject] else { return [] }
    var out: [(String, Double)] = []
    for s in services {
        let name = (IOHIDServiceClientCopyProperty(s, "Product" as CFString)?.takeRetainedValue() as? String) ?? "?"
        if let ev = IOHIDServiceClientCopyEvent(s, kTemperatureEvent, 0, 0)?.takeRetainedValue() {
            let t = IOHIDEventGetFloatValue(ev, kTemperatureField)
            if t > 0 && t < 130 { out.append((name, t)) }
        }
    }
    return out
}

let all = sensors()
// CPU die sensors: "PMU tdie..." on Apple Silicon (M1-M5), "TC..." style names elsewhere
var cpu = all.filter { $0.0.lowercased().contains("tdie") }.map { $0.1 }
if cpu.isEmpty { cpu = all.filter { $0.0.lowercased().contains("cpu") || $0.0.lowercased().contains("soc") }.map { $0.1 } }
let battery = all.filter { $0.0.lowercased().contains("batt") || $0.0.lowercased().contains("gas gauge") }.map { $0.1 }

let state: String
switch ProcessInfo.processInfo.thermalState {
case .nominal: state = "nominal"
case .fair: state = "fair"
case .serious: state = "serious"
case .critical: state = "critical"
@unknown default: state = "unknown"
}

func num(_ v: Double?) -> String { v.map { String(format: "%.1f", $0) } ?? "null" }
let cpuMax = cpu.max()
let cpuAvg = cpu.isEmpty ? nil : cpu.reduce(0, +) / Double(cpu.count)
print("{\"cpu\": \(num(cpuMax)), \"cpu_avg\": \(num(cpuAvg)), \"battery\": \(num(battery.max())), \"thermal\": \"\(state)\", \"sensors\": \(all.count)}")
