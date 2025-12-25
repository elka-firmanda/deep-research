import { Message, ProgressEvent } from '../lib/types'

interface ActiveStream {
  abortController: AbortController
  conversationId: string | null
  reader: ReadableStreamDefaultReader<Uint8Array>
  streamId: string
}

class StreamManager {
  private activeStreams = new Map<string, ActiveStream>()
  private messageId = 0

  startStream(
    streamId: string,
    abortController: AbortController,
    reader: ReadableStreamDefaultReader<Uint8Array>,
    conversationId: string | null
  ) {
    this.activeStreams.set(streamId, {
      abortController,
      reader,
      conversationId,
      streamId,
    })
  }

  getStream(streamId: string): ActiveStream | undefined {
    return this.activeStreams.get(streamId)
  }

  removeStream(streamId: string) {
    const stream = this.activeStreams.get(streamId)
    if (stream) {
      try {
        stream.reader.cancel()
      } catch (e) {
        console.error('Error cancelling reader:', e)
      }
      this.activeStreams.delete(streamId)
    }
  }

  abortStream(streamId: string) {
    const stream = this.activeStreams.get(streamId)
    if (stream) {
      stream.abortController.abort()
      try {
        stream.reader.cancel()
      } catch (e) {
        console.error('Error cancelling reader:', e)
      }
      this.removeStream(streamId)
    }
  }

  hasActiveStream(conversationId: string): boolean {
    return Array.from(this.activeStreams.values()).some(
      s => s.conversationId === conversationId
    )
  }

  hasAnyActiveStream(): boolean {
    return this.activeStreams.size > 0
  }

  generateId(): string {
    return `stream_${++this.messageId}_${Date.now()}`
  }
}

export const streamManager = new StreamManager()
