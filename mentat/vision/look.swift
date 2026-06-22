// look.swift — grab one webcam frame and run Apple's Vision face + human detection.
// Native AVFoundation + Vision: no installs, no model downloads, runs on the CPU/Neural Engine.
// Prints a single JSON line: {"faces":N,"people":M,"confidences":[...]}  (or {"error":"..."}).
import AVFoundation
import Vision
import Foundation

final class Grabber: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let session = AVCaptureSession()
    let queue = DispatchQueue(label: "cam")
    var frame = 0
    var done = false

    func start() -> Bool {
        guard let device = AVCaptureDevice.default(for: .video),
              let input = try? AVCaptureDeviceInput(device: device) else { return false }
        session.beginConfiguration()
        guard session.canAddInput(input) else { return false }
        session.addInput(input)
        let out = AVCaptureVideoDataOutput()
        out.setSampleBufferDelegate(self, queue: queue)
        guard session.canAddOutput(out) else { return false }
        session.addOutput(out)
        session.commitConfiguration()
        session.startRunning()
        return true
    }

    func captureOutput(_ o: AVCaptureOutput, didOutput buf: CMSampleBuffer, from c: AVCaptureConnection) {
        if done { return }
        frame += 1
        if frame < 8 { return }                       // let exposure/white-balance settle
        guard let pb = CMSampleBufferGetImageBuffer(buf) else { return }
        done = true
        let faceReq = VNDetectFaceRectanglesRequest()
        let humanReq = VNDetectHumanRectanglesRequest()
        let handler = VNImageRequestHandler(cvPixelBuffer: pb, orientation: .up, options: [:])
        try? handler.perform([faceReq, humanReq])
        let faces = faceReq.results ?? []
        let people = humanReq.results?.count ?? 0
        let confs = faces.map { String(format: "%.3f", $0.confidence) }.joined(separator: ",")
        print("{\"faces\":\(faces.count),\"people\":\(people),\"confidences\":[\(confs)]}")
        session.stopRunning()
        exit(0)
    }
}

let g = Grabber()
if !g.start() { print("{\"error\":\"camera unavailable or access denied\"}"); exit(2) }
DispatchQueue.main.asyncAfter(deadline: .now() + 6) { print("{\"error\":\"timeout (no frame)\"}"); exit(3) }
RunLoop.main.run()
