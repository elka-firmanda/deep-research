import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { Message, ProgressEvent } from '../lib/types'

interface ChatContextType {
  conversationId: string | null
  setConversationId: (id: string | null) => void
  messages: Message[]
  setMessages: (messages: Message[]) => void
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  currentProgress: ProgressEvent | null
  setCurrentProgress: (progress: ProgressEvent | null) => void
  addMessage: (message: Message) => void
}

const ChatContext = createContext<ChatContextType | undefined>(undefined)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentProgress, setCurrentProgress] = useState<ProgressEvent | null>(null)

  useEffect(() => {
    const savedConversationId = localStorage.getItem('chat_conversation_id')
    const savedMessages = localStorage.getItem('chat_messages')
    const savedLoading = localStorage.getItem('chat_is_loading')
    const savedProgress = localStorage.getItem('chat_progress')

    if (savedConversationId) setConversationId(savedConversationId)
    if (savedMessages) {
      try {
        const parsed = JSON.parse(savedMessages)
        const messagesWithDates = parsed.map((m: Message) => ({
          ...m,
          timestamp: new Date(m.timestamp)
        }))
        setMessages(messagesWithDates)
      } catch (e) {
        console.error('Failed to parse saved messages:', e)
      }
    }
    // Restore loading state - if we were loading, keep it loading
    if (savedLoading) setIsLoading(savedLoading === 'true')
    if (savedProgress) {
      try {
        setCurrentProgress(JSON.parse(savedProgress))
      } catch (e) {
        console.error('Failed to parse saved progress:', e)
      }
    }
  }, [])

  useEffect(() => {
    localStorage.setItem('chat_conversation_id', conversationId || '')
  }, [conversationId])

  useEffect(() => {
    localStorage.setItem('chat_messages', JSON.stringify(messages))
  }, [messages])

  useEffect(() => {
    localStorage.setItem('chat_is_loading', isLoading.toString())
  }, [isLoading])

  useEffect(() => {
    localStorage.setItem('chat_progress', JSON.stringify(currentProgress))
  }, [currentProgress])

  const addMessage = (message: Message) => {
    setMessages(prev => [...prev, message])
  }

  return (
    <ChatContext.Provider
      value={{
        conversationId,
        setConversationId,
        messages,
        setMessages,
        isLoading,
        setIsLoading,
        currentProgress,
        setCurrentProgress,
        addMessage,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const context = useContext(ChatContext)
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider')
  }
  return context
}
