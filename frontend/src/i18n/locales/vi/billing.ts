/** 越南语：计费：支付弹窗、余额卡、用量/充值记录、余额不足提示 */

export const viBilling = {
  billing: {
    topupLink: 'Nạp tiền →',
    topup: 'Nạp tiền',
    alertTitle: 'Thông báo chi tiêu',
    insufficientTitle: 'Số dư không đủ',
    insufficientMessage: 'Số dư không đủ để bắt đầu tạo. Hãy nạp thêm tiền trước.',
    creditAmount: 'Bạn nhận được {amount}',
    usageCard: {
      title: 'Đã dùng tháng này',
      subtitle: 'Tính theo số token thực tế của nhà cung cấp mô hình',
      tokens: 'Token đã dùng',
      monthCharge: 'Chi phí tháng này',
      frozen: 'Tạm giữ',
      calls: '{count} lượt gọi',
    },
    wallet: {
      frozenAmount: 'Tạm giữ',
      viewHistory: 'Xem lịch sử nạp',
    },
    transfer: {
      title: 'Nạp tiền bằng chuyển khoản',
      amount: 'Số tiền cần chuyển',
      bankName: 'Ngân hàng',
      account: 'Số tài khoản',
      holder: 'Chủ tài khoản',
      note: 'Nội dung chuyển khoản',
      noteHint: 'Bắt buộc ghi đúng mã đơn này vào nội dung chuyển khoản. Chúng tôi dựa vào mã này để đối chiếu và cộng tiền vào số dư',
      qrAlt: 'Mã VietQR chuyển khoản',
      scanHint: 'Quét mã VietQR bằng ứng dụng ngân hàng',
      expiresIn: 'Đơn hết hạn sau {time}',
      expired: 'Đơn nạp đã hết hạn. Hãy đóng và tạo đơn mới.',
      confirmHint:
        'Sau khi bạn chuyển khoản, chúng tôi sẽ kiểm tra và cộng tiền vào số dư, thường trong 1 ngày làm việc. Theo dõi tại Lịch sử nạp.',
      waiting: 'Đang chờ xác nhận chuyển khoản',
      paidWait: 'Đã nhận chuyển khoản. Tiền đã cộng vào số dư.',
      closed: 'Đơn đã đóng',
      copy: 'Sao chép',
      copied: 'Đã sao chép',
      transferred: 'Tôi đã chuyển khoản',
      cancel: 'Hủy đơn',
      done: 'Xong',
    },
    history: {
      empty: 'Chưa có lịch sử nạp',
      orderStatus: {
        pending: 'Chờ xác nhận',
        paid: 'Đã cộng vào số dư',
        closed: 'Đã đóng',
      },
    },
    records: {
      title: 'Lịch sử trừ tiền',
      subtitle: 'Số token và chi phí của từng lượt gọi AI',
      loadFailed: 'Không tải được lịch sử trừ tiền',
      empty: 'Chưa có khoản trừ tiền nào',
      estimated: 'ước tính',
      pagination: 'Phân trang lịch sử trừ tiền',
    },
  },
} as const
