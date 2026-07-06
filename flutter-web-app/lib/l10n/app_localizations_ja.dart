// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Japanese (`ja`).
class AppLocalizationsJa extends AppLocalizations {
  AppLocalizationsJa([String locale = 'ja']) : super(locale);

  @override
  String get appTitle => 'gen-fashion';

  @override
  String get navCloset => 'クローゼット';

  @override
  String get navCoordinate => 'コーディネート';

  @override
  String get navHistory => '履歴';

  @override
  String get navShared => '共有';

  @override
  String get appHelpTooltip => 'このアプリの使い方';

  @override
  String get appHelpTitle => 'このアプリの使い方';

  @override
  String get signOut => 'サインアウト';

  @override
  String get language => '言語';

  @override
  String get languageJapanese => '日本語';

  @override
  String get languageEnglish => 'English';

  @override
  String get loginEyebrow => 'パーソナルスタイリング';

  @override
  String get loginSubtitle => 'サインインしてクローゼットを管理しましょう。';

  @override
  String get signInLocal => 'ローカルでサインイン';

  @override
  String get signInGoogle => 'Google でサインイン';

  @override
  String get signingIn => 'サインイン中...';

  @override
  String signInFailed(Object error) {
    return 'サインインに失敗しました: $error';
  }

  @override
  String get closetTitle => 'クローゼット';

  @override
  String get closetHelpPurpose =>
      'クローゼットには、所有している服や気になっている服の写真を最大20点まで保存できます。コーディネートはこれらのアイテムを使って全身コーデを作ります。';

  @override
  String get closetHelpUpload =>
      '「アイテムを追加」をタップして写真をアップロードすると、カテゴリ・色・季節・タグが自動で解析されます。鉛筆アイコンからいつでも編集できます。';

  @override
  String get closetHelpFilters =>
      '上部のフィルターで絞り込めます。「所有」と「気になる」は、すでに持っているアイテムと保存した候補を切り替え、カテゴリチップはその中でさらに絞り込みます。';

  @override
  String get emptyClosetHelpHint => 'はじめての方は、上部の ⓘ アイコンをタップしてください。';

  @override
  String get addItem => 'アイテムを追加';

  @override
  String get uploading => 'アップロード中...';

  @override
  String get uploadQueued => 'アップロードを受け付けました。解析中です...';

  @override
  String get closetFull => 'クローゼットは上限です（20アイテム）。';

  @override
  String uploadFailed(Object error) {
    return 'アップロードに失敗しました: $error';
  }

  @override
  String get deleteItemQuestion => 'アイテムを削除しますか？';

  @override
  String get deleteItemBody => 'このアイテムをクローゼットから削除します。';

  @override
  String get deleteHistoryQuestion => '画像を削除しますか？';

  @override
  String get deleteHistoryBody => '生成画像を履歴から削除します。';

  @override
  String get cancel => 'キャンセル';

  @override
  String get delete => '削除';

  @override
  String deleteFailed(Object error) {
    return '削除に失敗しました: $error';
  }

  @override
  String get editMetadata => 'アイテム情報を編集';

  @override
  String get category => 'カテゴリ';

  @override
  String get colorsComma => '色（カンマ区切り）';

  @override
  String get season => '季節';

  @override
  String get tagsComma => 'タグ（カンマ区切り）';

  @override
  String get gender => '性別';

  @override
  String get genderCommon => '共通';

  @override
  String get genderFemale => '女性';

  @override
  String get genderMale => '男性';

  @override
  String get save => '保存';

  @override
  String updateFailed(Object error) {
    return '更新に失敗しました: $error';
  }

  @override
  String get emptyCloset => '最初のアイテムを追加しましょう。';

  @override
  String get unknown => '不明';

  @override
  String get analyzing => '解析中...';

  @override
  String get analysisFailed => '解析に失敗しました';

  @override
  String get statusProcessing => 'PROCESSING';

  @override
  String get statusReady => 'READY';

  @override
  String get statusError => 'ERROR';

  @override
  String get statusUnknown => 'UNKNOWN';

  @override
  String get deleteTooltip => '削除';

  @override
  String get editMetadataTooltip => 'メタデータを編集';

  @override
  String get coordinationTitle => 'コーディネート';

  @override
  String get helpCoordinateIntro => 'スタイリングのモードと服の取得元を選んで、全身コーデを生成します。';

  @override
  String get modeStandard => 'クローゼットコーデ';

  @override
  String get modeAssisted => '買い足し提案';

  @override
  String get modeStandardHint => 'クローゼットの服だけで全身コーデを作ります。';

  @override
  String get modeAssistedHint =>
      '手持ちの服（最大3点）を選ぶと、AIが楽天で購入できるアイテムを含めた全身コーデを提案します。';

  @override
  String get analyzingItem => '解析中...';

  @override
  String get anchorItemsLabel => '自分の服（最大3点）';

  @override
  String get anchorLimitReached => '選択できるのは最大3点です。';

  @override
  String get noReadyAnchorItems => '利用できるアイテムがまだありません。アップロードしてください。';

  @override
  String get sourceRakuten => '楽天';

  @override
  String get addToCloset => 'クローゼットに追加';

  @override
  String get savedAsInteresting => '「気になる」に保存しました';

  @override
  String importFailed(Object error) {
    return '保存に失敗しました: $error';
  }

  @override
  String get coordinateReadyNotification => 'コーディネートが完成しました。';

  @override
  String get coordinateFailedNotification => 'コーディネートの生成に失敗しました。';

  @override
  String get viewAction => '表示';

  @override
  String get coordinateCompletedTitle => 'コーディネートが完成しました';

  @override
  String get coordinateCompletedBody =>
      'この結果は履歴からも確認できます。別の服で新しいコーディネートを始められます。';

  @override
  String get startNewCoordinate => '新しいコーディネートを始める';

  @override
  String get openProductPage => '商品ページを開く';

  @override
  String get saveInterestingDialogTitle => '楽天の商品をクローゼットに保存しますか?';

  @override
  String get saveInterestingDialogBody =>
      'このコーディネートに含まれる楽天の商品です。気に入ったものを「気になる」として保存できます。';

  @override
  String get saveInterestingSkip => 'スキップ';

  @override
  String get saveInterestingConfirm => '選択した商品を保存';

  @override
  String get ownership => '所有状況';

  @override
  String get ownershipOwned => '所有';

  @override
  String get ownershipInteresting => '気になる';

  @override
  String get ownershipOwnedHint => 'すでに所有しているアイテムです。';

  @override
  String get ownershipInterestingHint => 'まだ購入していない、保存した候補です。';

  @override
  String get filterAll => 'すべて';

  @override
  String get noItemsMatchFilter => '条件に一致するアイテムがありません。';

  @override
  String get sourceShared => '共有';

  @override
  String get sourceMine => '自分';

  @override
  String get sourceSharedHint => '共有クローゼットのデモアイテムを使います。アップロード不要です。';

  @override
  String get sourceMineHint => '自分のクローゼットのアイテムを使います。';

  @override
  String get sharedCloset => '共有クローゼット';

  @override
  String get occasion => '用途';

  @override
  String get style => 'スタイル';

  @override
  String get colors => '色';

  @override
  String selectedGenerationLanguage(Object language) {
    return '生成言語: $language';
  }

  @override
  String get running => '実行中';

  @override
  String get start => '開始';

  @override
  String get agentTrace => 'エージェントの流れ';

  @override
  String errorWithMessage(Object error) {
    return 'エラー: $error';
  }

  @override
  String get noSessionEvents => 'まだセッションイベントはありません。';

  @override
  String get chooseItems => 'アイテムを選択';

  @override
  String get generateSelected => '選択したアイテムで生成';

  @override
  String get recommended => 'おすすめ';

  @override
  String get item => 'アイテム';

  @override
  String get result => '結果';

  @override
  String get coordinatePlaceholder => 'ここにコーディネート画像が表示されます。';

  @override
  String traceSearchedCloset(Object agentName, Object count) {
    return '$agentName がクローゼットを検索しました - $count 件';
  }

  @override
  String traceSearchingCloset(Object agentName) {
    return '$agentName がクローゼットを検索中';
  }

  @override
  String traceGeneratedCoordinate(Object agentName) {
    return '$agentName がコーディネートを生成しました';
  }

  @override
  String traceGeneratingCoordinate(Object agentName) {
    return '$agentName がコーディネートを生成中';
  }

  @override
  String get tracePreview => 'プレビュー';

  @override
  String get traceRaw => 'Raw';

  @override
  String get traceDescription => '説明';

  @override
  String get traceStyleDirection => 'スタイル';

  @override
  String get traceWearer => '着用者';

  @override
  String get traceItemCount => 'アイテム数';

  @override
  String get traceModelUsed => 'モデル';

  @override
  String get traceGenerationPrompt => 'プロンプト';

  @override
  String get traceTags => 'タグ';

  @override
  String get traceTargetAgent => 'エージェント';

  @override
  String traceItemsFound(int count) {
    return '$count 件見つかりました';
  }

  @override
  String get traceQuery => '検索キーワード';

  @override
  String get traceShopName => '店舗';

  @override
  String traceSearchingRakuten(Object agentName) {
    return '$agentName が楽天を検索中';
  }

  @override
  String traceSearchedRakuten(Object agentName, Object count) {
    return '$agentName が楽天を検索しました - $count 件';
  }

  @override
  String historyLoadFailed(Object error) {
    return '履歴の読み込みに失敗しました: $error';
  }

  @override
  String get historyEmpty => '完了したコーディネートはまだありません。';

  @override
  String get helpHistoryBody => '履歴には、これまでに生成したコーディネートが新しい順に並びます。';

  @override
  String get dateUnavailable => '日付不明';

  @override
  String get myCloset => '自分のクローゼット';

  @override
  String sharedGalleryError(Object error) {
    return 'エラー: $error';
  }

  @override
  String get sharedAttribution =>
      '共有クローゼットの画像は Clothing Dataset (CC BY-SA 4.0) を使用しています';

  @override
  String get sharedAboutBody =>
      '共有クローゼットにはサンプルの服の写真が入っており、自分の服をアップロードしなくても、すぐにスタイリングのデモを体験できます。';

  @override
  String get sharedAboutDataset => '画像素材: Clothing Dataset (CC BY-SA 4.0)';

  @override
  String get sharedAboutAuthor => '著作者: Alexey Grigorev';

  @override
  String get viewDataset => 'Kaggle でデータセットを見る';

  @override
  String get close => '閉じる';
}
