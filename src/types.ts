/** Tek bir sıkça sorulan soruyu temsil eder */
export interface FAQItem {
    question: string;
    answer: string;
}

/** Sayfaya özgü SSS'lerin ve kullanıcı tipinin yapısını tanımlar */
export interface PageFAQs {
    [pageKey: string]: {
        ktype: 'ogrenci' | 'personel'; // Zorunlu kullanıcı tipi
        faqs: FAQItem[];
    };
}

/** Mesaj aksiyon türlerini tanımlar */
export type ActionType = 'link';

/** Kullanıcı ve bot arasındaki mesaj yapısını tanımlar */
export interface Message {
    role: 'user' | 'assistant';
    content: string;
    action?: {
        type: ActionType;
        url: string;
        buttonText: string;
    };
}

/** Chatbotun kullanıcıya sunduğu seçenekleri temsil eder */
export interface Option {
    text: string;
    payload: string;
}

/** Botun API'den döndürdüğü yanıtın yapısını tanımlar */
export interface BotResponseData {
    message?: {
        content: string;
    };
    type: 'normal' | 'reset_and_continue' | 'continuation_prompt' | 'resolution_prompt' | 'redirect' | 'end_chat' | 'message_chunk' | 'done' | 'error';
    url?: string;
    options?: Option[];
    content?: string; // Stream mesaj parçası için
    detail?: string; // Hata mesajı için
}